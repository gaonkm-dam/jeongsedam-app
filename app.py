# 정세담 정책 프로그램 - 단일 파일 버전 (Streamlit Cloud 호환)
# modules, config 없이 모든 기능 통합

import streamlit as st
import os
import json
import sqlite3
import base64
from datetime import datetime, date
from io import BytesIO
from typing import Dict, Any, Optional, List, Tuple
from contextlib import contextmanager
from zipfile import ZipFile
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# OpenAI import
try:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and hasattr(st, 'secrets'):
        api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        st.error("⚠️ OPENAI_API_KEY가 설정되지 않았습니다. Streamlit Cloud Secrets에서 설정하세요.")
        st.stop()
    client = OpenAI(api_key=api_key)
except Exception as e:
    st.error(f"OpenAI 라이브러리 로드 실패: {e}")
    st.stop()

# PIL import
try:
    from PIL import Image
except:
    st.error("Pillow 라이브러리가 필요합니다. requirements.txt에 pillow>=10.0.0 추가하세요.")
    st.stop()

# ReportLab import
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
except:
    st.error("ReportLab 라이브러리가 필요합니다. requirements.txt에 reportlab>=4.0.0 추가하세요.")
    st.stop()

# ==================== 설정 (Settings) ====================

DB_PATH = "data/policies.db"

TARGET_AUDIENCES = {
    "시민": {
        "tone": "친근하고 이해하기 쉬운",
        "focus": "일상 생활 혜택, 실생활 변화"
    },
    "청년": {
        "tone": "트렌디하고 직관적인",
        "focus": "기회 확대, 미래 전망"
    },
    "노인": {
        "tone": "친절하고 따뜻한",
        "focus": "안전, 편의성, 접근성"
    },
    "학부모": {
        "tone": "신뢰감 있고 구체적인",
        "focus": "자녀 안전, 교육 효과"
    },
    "기업": {
        "tone": "전문적이고 효율적인",
        "focus": "비용 절감, 규제 완화, ROI"
    },
    "지자체 공무원": {
        "tone": "체계적이고 실무적인",
        "focus": "실행 가능성, 예산, 법적 근거"
    },
    "의회/의원": {
        "tone": "설득적이고 근거 중심",
        "focus": "정책 효과, 국민 체감, 성과 지표"
    }
}

VIDEO_PLATFORMS = {
    "Sora": "https://sora.chatgpt.com",
    "Runway": "https://runwayml.com",
    "Pika": "https://pika.art",
    "Luma Dream Machine": "https://lumalabs.ai"
}

IMAGE_SIZES = ["1024x1024", "1024x1792", "1792x1024"]
VIDEO_DURATIONS = ["10초", "20초", "30초", "60초"]

CONTENT_PACKAGES = {
    "A 마케팅": ["이미지 2장", "영상 1개", "홍보 문구 3종"],
    "B 정책 설명": ["정책 요약", "PPT 구성", "FAQ"],
    "C 풀 패키지": ["이미지 4장", "영상 2개", "홍보 문구 5종", "정책 문서", "PPT", "성과 지표"]
}

DEFAULT_IMAGE_STYLE = """
PHOTO-REALISTIC Korean documentary style. Shot on Canon EOS R5, 35mm f/1.8, natural daylight.

Korean People: Natural Korean faces, realistic skin texture, genuine expressions, casual Korean clothing (NOT costumes). Ages 20s-60s with natural features. NO AI artifacts, NO perfect symmetry, NO filtered faces.

Location: Real Korean settings - apartments, offices, parks, cafes (Seoul/Busan style). Modern Korean architecture (2010s-2020s). Background: Korean streetscape, but NO readable text/signs.

Lighting: Soft natural light (morning/afternoon), realistic shadows, true Korean colors (neutral tones, NO oversaturation, NO HDR).

Composition: Eye-level, candid moment, subject sharp with subtle background blur. Documentary photography aesthetic.

FORBIDDEN: ❌ Cartoon/illustration/anime style ❌ 3D render ❌ Sci-fi/fantasy ❌ Stock photo poses ❌ Heavy makeup ❌ Studio lighting ❌ Visible text ❌ Foreign locations

Reference: Korean TV drama stills (Reply 1988, My Mister), Korean photojournalism (한겨레/경향신문).

MUST look like: Real photo taken in Korea TODAY with professional camera.
"""

# ==================== 데이터베이스 (Database) ====================

@contextmanager
def get_db():
    # data 폴더가 없으면 생성
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                target_audience TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                content_data TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                view_count INTEGER DEFAULT 0,
                engagement_score REAL DEFAULT 0.0,
                feedback_data TEXT,
                metrics_data TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                media_url TEXT,
                media_data BLOB,
                prompt TEXT,
                generation_params TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.commit()

def create_policy(title: str, category: str, target_audience: str, description: str = "") -> int:
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO policies (title, category, target_audience, description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'draft', ?, ?)
        """, (title, category, target_audience, description, now, now))
        conn.commit()
        return cursor.lastrowid

def update_policy_status(policy_id: int, status: str):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            UPDATE policies SET status = ?, updated_at = ? WHERE id = ?
        """, (status, now, policy_id))
        conn.commit()

def save_policy_content(policy_id: int, content_type: str, content_data: Dict[str, Any], metadata: Optional[Dict] = None):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO policy_contents (policy_id, content_type, content_data, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            policy_id,
            content_type,
            json.dumps(content_data, ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False),
            now
        ))
        conn.commit()

def save_generated_media(policy_id: int, media_type: str, media_data: bytes, prompt: str, params: Dict[str, Any]):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO generated_media (policy_id, media_type, media_data, prompt, generation_params, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            policy_id,
            media_type,
            media_data,
            prompt,
            json.dumps(params, ensure_ascii=False),
            now
        ))
        conn.commit()

def get_policy(policy_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
        if row:
            return dict(row)
        return None

def get_all_policies(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

def get_policy_contents(policy_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policy_contents WHERE policy_id = ? ORDER BY created_at DESC
        """, (policy_id,)).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            data['content_data'] = json.loads(data['content_data'])
            data['metadata'] = json.loads(data['metadata']) if data['metadata'] else {}
            results.append(data)
        return results

def get_generated_media(policy_id: int, media_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        if media_type:
            rows = conn.execute("""
                SELECT * FROM generated_media WHERE policy_id = ? AND media_type = ? ORDER BY created_at DESC
            """, (policy_id, media_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM generated_media WHERE policy_id = ? ORDER BY created_at DESC
            """, (policy_id,)).fetchall()
        
        results = []
        for row in rows:
            data = dict(row)
            data['generation_params'] = json.loads(data['generation_params']) if data['generation_params'] else {}
            results.append(data)
        return results

def get_policies_by_date(date_str: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies 
            WHERE date(created_at) = date(?)
            ORDER BY created_at DESC
        """, (date_str,)).fetchall()
        return [dict(row) for row in rows]

def get_policies_by_date_range(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies 
            WHERE date(created_at) BETWEEN date(?) AND date(?)
            ORDER BY created_at DESC
        """, (start_date, end_date)).fetchall()
        return [dict(row) for row in rows]

# ==================== AI 엔진 (AI Engine) ====================

def parse_json_response(text: str) -> Optional[Dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except:
        return None

def generate_policy_analysis(
    title: str,
    category: str,
    target_audience: str,
    description: str,
    keywords: str = "",
    constraints: str = "",
    model: str = "gpt-4o"
) -> Tuple[Optional[Dict], str]:
    
    prompt = f"""
당신은 정세담 정책 자동화 시스템의 AI입니다.
정책의 기획부터 실행, 홍보, 성과관리까지 전체 프로세스를 설계합니다.

[입력 정보]
정책 제목: {title}
정책 카테고리: {category}
대상: {target_audience}
정책 설명: {description}
강조 키워드: {keywords}
제약 조건: {constraints}

[출력 규칙]
- 반드시 JSON 형식으로만 출력
- 한국 현실에 맞는 실행 가능한 내용
- 과장 금지, 측정 가능한 지표 사용
- 대상에 맞는 톤과 메시지

[JSON 스키마]
{{
  "policy_planning": {{
    "objective": "정책 목표 (3-5문장)",
    "target_analysis": "대상 분석 (니즈, 특성, 접근법 3-5문장)",
    "key_strategies": ["핵심 전략 5-8개"],
    "expected_outcomes": ["기대 효과 5-7개"],
    "timeline": {{
      "preparation": "준비 단계 내용",
      "pilot": "시범 운영 내용",
      "expansion": "확대 적용 내용"
    }}
  }},
  
  "execution_plan": {{
    "action_items": [
      {{
        "phase": "단계명",
        "action": "실행 내용",
        "responsible": "담당 주체",
        "timeline": "소요 기간"
      }}
    ],
    "resources_needed": {{
      "budget_range": "예산 범위 (구체적 금액 대신 범주)",
      "personnel": "필요 인력",
      "infrastructure": "필요 인프라"
    }},
    "risk_management": [
      {{
        "risk": "리스크 항목",
        "impact": "영향도",
        "mitigation": "완화 방안"
      }}
    ]
  }},
  
  "communication_strategy": {{
    "key_messages": ["핵심 메시지 5-8개"],
    "channels": [
      {{
        "channel": "채널명",
        "content_type": "콘텐츠 형식",
        "frequency": "발행 주기"
      }}
    ],
    "target_specific_messages": {{
      "citizens": "시민 대상 메시지",
      "youth": "청년 대상 메시지",
      "elderly": "노인 대상 메시지",
      "parents": "학부모 대상 메시지"
    }}
  }},
  
  "content_briefs": {{
    "image_brief_1": {{
      "concept": "이미지 컨셉 (5-7문장)",
      "scene_description": "장면 상세 묘사 (10-15문장)",
      "visual_style": "비주얼 스타일 (촬영 기법, 조명, 색감)",
      "key_message": "전달할 핵심 메시지"
    }},
    "image_brief_2": {{
      "concept": "이미지 컨셉 (5-7문장)",
      "scene_description": "장면 상세 묘사 (10-15문장)",
      "visual_style": "비주얼 스타일 (촬영 기법, 조명, 색감)",
      "key_message": "전달할 핵심 메시지"
    }},
    "video_brief": {{
      "duration": "영상 길이",
      "narrative_arc": "스토리 구조 (5-8문장)",
      "scenes": [
        {{
          "timestamp": "시간대",
          "scene": "장면 내용",
          "visuals": "비주얼 요소",
          "audio": "오디오 (내레이션/음악/효과음)",
          "message": "전달 메시지"
        }}
      ],
      "style_guide": "영상 스타일 가이드",
      "call_to_action": "행동 유도 문구"
    }}
  }},
  
  "marketing_materials": {{
    "slogan": "슬로건 (20-30자)",
    "tagline": "태그라인 (40-60자)",
    "elevator_pitch": "엘리베이터 피치 (150-200자)",
    "press_release": "보도자료 형식 (300-500자)",
    "social_media_posts": [
      {{
        "platform": "플랫폼",
        "content": "게시물 내용",
        "hashtags": ["해시태그"]
      }}
    ],
    "faq": [
      {{
        "question": "자주 묻는 질문",
        "answer": "답변"
      }}
    ]
  }},
  
  "performance_metrics": {{
    "kpi_framework": [
      {{
        "category": "지표 카테고리",
        "metric": "측정 항목",
        "measurement_method": "측정 방법",
        "target_range": "목표 범위 (구간/추이)",
        "data_source": "데이터 출처"
      }}
    ],
    "success_criteria": ["성공 기준 5-7개"],
    "monitoring_plan": {{
      "daily": "일간 모니터링 항목",
      "weekly": "주간 모니터링 항목",
      "monthly": "월간 모니터링 항목"
    }},
    "improvement_triggers": ["개선이 필요한 시점을 알리는 지표 5-7개"]
  }},
  
  "stakeholder_management": {{
    "stakeholders": [
      {{
        "group": "이해관계자 그룹",
        "interests": "관심사",
        "engagement_strategy": "소통 전략"
      }}
    ],
    "objection_handling": [
      {{
        "objection": "예상 반대 의견",
        "response": "대응 논리"
      }}
    ]
  }}
}}

위 스키마를 정확히 따라 JSON만 출력하세요.
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 정책 전문가입니다. 항상 JSON 형식으로만 응답합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        raw_text = response.choices[0].message.content
        parsed_data = parse_json_response(raw_text)
        
        if parsed_data:
            return parsed_data, raw_text
        
        # JSON 파싱 실패시 재시도
        retry_prompt = f"""
이전 응답이 올바른 JSON 형식이 아닙니다.
아래 내용을 완벽한 JSON으로 다시 출력해주세요.

{raw_text}
"""
        
        retry_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "JSON 형식으로만 응답합니다."},
                {"role": "user", "content": retry_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        retry_text = retry_response.choices[0].message.content
        retry_parsed = parse_json_response(retry_text)
        
        return retry_parsed, retry_text
        
    except Exception as e:
        return None, f"Error: {str(e)}"

def generate_image_prompt(brief: Dict[str, Any], style_override: str = "") -> str:
    concept = brief.get("concept", "")
    scene = brief.get("scene_description", "")
    style = brief.get("visual_style", "")
    message = brief.get("key_message", "")
    
    base_style = style_override if style_override else DEFAULT_IMAGE_STYLE
    
    prompt = f"""
{concept}

Scene description: {scene}

Visual style: {style}

{base_style}

Key message to convey: {message}

Important: Create realistic Korean people with natural, undistorted facial features.
No text or writing should appear anywhere in the image.
Focus on authentic Korean urban/suburban environment and genuine human expressions.
"""
    
    return prompt.strip()

def generate_video_prompts_3styles(brief: Dict[str, Any]) -> Dict[str, str]:
    """10초 영상 3가지 스타일 프롬프트 생성"""
    
    narrative = brief.get("narrative_arc", "")
    cta = brief.get("call_to_action", "")
    
    base_context = f"""
Duration: 10 seconds
Location: Modern South Korea
Language: Korean subtitles only
No English text visible
"""
    
    # 스타일 1: 다큐멘터리
    style1 = f"""
[스타일 1: 다큐멘터리 리얼리즘]

{base_context}

Visual Style:
- Handheld camera feel, natural movements
- Realistic lighting, documentary aesthetic
- Authentic Korean street scenes and people
- Observational approach, fly-on-the-wall style
- Natural color grading with slight desaturation

Camera:
- Medium shots and close-ups
- Slight camera shake for realism
- Follow subjects naturally

Audio:
- Natural ambient sounds (traffic, voices, city sounds)
- Minimal background music
- Natural Korean dialogue or voice-over

Narrative: {narrative}

Mood: Authentic, grounded, trustworthy
Pacing: Steady, observational
Final Message: {cta}

Technical: 24fps, cinematic aspect ratio, professional documentary style
"""
    
    # 스타일 2: 시네마틱
    style2 = f"""
[스타일 2: 시네마틱 드라마]

{base_context}

Visual Style:
- Smooth cinematic camera movements (gimbal/slider)
- Dramatic lighting with warm and cool tones
- Korean urban landscape with cinematic composition
- Establishing shots of Seoul skyline or modern architecture
- Rich color grading inspired by Korean cinema

Camera:
- Wide establishing shots
- Slow push-ins and reveals
- Overhead/drone shots of Korean cityscape
- Smooth tracking shots

Audio:
- Emotional background music (orchestral or modern Korean OST style)
- Carefully designed sound effects
- Polished voice-over narration

Narrative: {narrative}

Mood: Inspiring, emotional, aspirational
Pacing: Dynamic with emotional beats
Final Message: {cta}

Technical: 24fps, anamorphic feel, cinematic color grade
"""
    
    # 스타일 3: 모던 다이내믹
    style3 = f"""
[스타일 3: 모던 다이내믹]

{base_context}

Visual Style:
- Fast-paced dynamic cuts
- Modern Korean lifestyle and technology
- Bright, energetic visuals
- Clean, contemporary aesthetic
- Vibrant color grading with saturated tones

Camera:
- Quick cuts between multiple angles
- Time-lapse of Korean city life
- Dynamic camera movements
- Close-ups on details and faces
- Match cuts for visual rhythm

Audio:
- Upbeat modern Korean music
- Rhythmic sound design
- Quick voice-over or on-screen Korean text animations
- Sync with visual cuts

Narrative: {narrative}

Mood: Energetic, modern, forward-thinking
Pacing: Fast, rhythmic, attention-grabbing
Final Message: {cta}

Technical: 30fps or 60fps slow-motion elements, high contrast, vibrant colors
"""
    
    return {
        "documentary": style1,
        "cinematic": style2,
        "modern_dynamic": style3
    }

# ==================== 이미지 생성 (Image Generator) ====================

def generate_policy_image(
    brief: dict,
    size: str = "1024x1024",
    quality: str = "standard"
) -> Optional[Tuple[Image.Image, bytes]]:
    """정책 이미지 생성 (brief 기반)"""
    
    prompt = generate_image_prompt(brief)
    
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
            response_format="b64_json"
        )
        
        if response.data and len(response.data) > 0:
            b64_data = response.data[0].b64_json
            image_bytes = base64.b64decode(b64_data)
            image = Image.open(BytesIO(image_bytes))
            return (image, image_bytes)
        
        return None
        
    except Exception as e:
        st.error(f"이미지 생성 실패: {str(e)}")
        return None

def batch_generate_images(prompts: List[str], size: str = "1024x1024", quality: str = "standard") -> List[Tuple[Image.Image, bytes]]:
    """여러 이미지 순차 생성"""
    results = []
    for prompt in prompts:
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
                response_format="b64_json"
            )
            
            if response.data and len(response.data) > 0:
                b64_data = response.data[0].b64_json
                image_bytes = base64.b64decode(b64_data)
                image = Image.open(BytesIO(image_bytes))
                results.append((image, image_bytes))
        except Exception as e:
            st.error(f"이미지 생성 실패: {str(e)}")
            continue
    
    return results

# ==================== PDF/ZIP 내보내기 (Export Manager) ====================

def create_pdf_report(policy: Dict[str, Any], analysis: Dict[str, Any], images: List[bytes] = None, video_prompts: List[str] = None) -> bytes:
    """한글 정책 보고서 PDF 생성 - AI 분석 9개 항목 전체 포함"""
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # 한글 폰트
    try:
        pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
        font_name = 'HYSMyeongJo-Medium'
    except:
        font_name = 'Helvetica'
    
    def new_page():
        c.showPage()
        return height - 50
    
    def add_heading(y, text, size=14):
        if y < 100:
            y = new_page()
        c.setFont(font_name, size)
        c.drawString(50, y, text[:90])
        return y - (size + 15)
    
    def add_text(y, text, size=10, indent=60):
        if y < 80:
            y = new_page()
        c.setFont(font_name, size)
        max_len = 85 if indent == 60 else 90
        lines = [text[i:i+max_len] for i in range(0, min(len(text), 400), max_len)]
        for line in lines[:10]:
            if y < 60:
                y = new_page()
                c.setFont(font_name, size)
            c.drawString(indent, y, line)
            y -= (size + 4)
        return y - 5
    
    y = height - 50
    
    # 표지
    c.setFont(font_name, 24)
    c.drawString(50, y, "정책 보고서")
    y -= 50
    c.setFont(font_name, 14)
    c.drawString(50, y, f"제목: {policy.get('title', '')[:50]}")
    y -= 25
    c.setFont(font_name, 11)
    c.drawString(50, y, f"카테고리: {policy.get('category', '')[:60]}")
    y -= 20
    c.drawString(50, y, f"대상: {policy.get('target_audience', '')}")
    y -= 20
    c.drawString(50, y, f"생성일: {policy.get('created_at', '')}")
    
    if not analysis:
        c.save()
        buffer.seek(0)
        return buffer.read()
    
    y = new_page()
    
    # ===== 1. 정책 기획 =====
    y = add_heading(y, "1. 정책 기획", 16)
    if "policy_planning" in analysis:
        planning = analysis["policy_planning"]
        
        if planning.get("objective"):
            y = add_text(y, f"[목표] {planning['objective']}", 10, 60)
        
        if planning.get("target_analysis"):
            y = add_text(y, f"[대상 분석] {planning['target_analysis']}", 10, 60)
        
        if planning.get("key_strategies"):
            y = add_text(y, "[핵심 전략]", 11, 60)
            for idx, s in enumerate(planning["key_strategies"][:8], 1):
                y = add_text(y, f"{idx}. {s}", 10, 70)
        
        if planning.get("expected_outcomes"):
            y = add_text(y, "[기대 효과]", 11, 60)
            for o in planning["expected_outcomes"][:5]:
                y = add_text(y, f"• {o}", 10, 70)
    
    y -= 15
    
    # ===== 2. 실행 계획 =====
    if y < 150:
        y = new_page()
    y = add_heading(y, "2. 실행 계획", 16)
    if "execution_plan" in analysis:
        execution = analysis["execution_plan"]
        
        if execution.get("action_items"):
            y = add_text(y, "[실행 항목]", 11, 60)
            for idx, item in enumerate(execution["action_items"][:8], 1):
                y = add_text(y, f"{idx}. {item.get('action', '')}", 10, 70)
        
        if execution.get("resources_needed"):
            res = execution["resources_needed"]
            y = add_text(y, "[필요 자원]", 11, 60)
            if res.get("budget_range"):
                y = add_text(y, f"예산: {res['budget_range']}", 10, 70)
            if res.get("personnel"):
                y = add_text(y, f"인력: {res['personnel']}", 10, 70)
    
    y -= 15
    
    # ===== 3. 커뮤니케이션 전략 =====
    if y < 150:
        y = new_page()
    y = add_heading(y, "3. 커뮤니케이션 전략", 16)
    if "communication_strategy" in analysis:
        comm = analysis["communication_strategy"]
        
        if comm.get("key_messages"):
            y = add_text(y, "[핵심 메시지]", 11, 60)
            for idx, msg in enumerate(comm["key_messages"][:8], 1):
                y = add_text(y, f"{idx}. {msg}", 10, 70)
        
        if comm.get("channels"):
            y = add_text(y, "[채널 전략]", 11, 60)
            for ch in comm["channels"][:5]:
                y = add_text(y, f"• {ch.get('channel', '')}: {ch.get('content_type', '')}", 10, 70)
    
    y -= 15
    
    # ===== 4. 콘텐츠 제작 브리프 =====
    if y < 150:
        y = new_page()
    y = add_heading(y, "4. 콘텐츠 제작 브리프", 16)
    if "content_briefs" in analysis:
        briefs = analysis["content_briefs"]
        
        if "image_brief_1" in briefs:
            b1 = briefs["image_brief_1"]
            y = add_text(y, "[이미지 브리프 1]", 11, 60)
            y = add_text(y, f"컨셉: {b1.get('concept', '')}", 10, 70)
            y = add_text(y, f"장면: {b1.get('scene_description', '')}", 10, 70)
        
        if "image_brief_2" in briefs:
            b2 = briefs["image_brief_2"]
            y = add_text(y, "[이미지 브리프 2]", 11, 60)
            y = add_text(y, f"컨셉: {b2.get('concept', '')}", 10, 70)
            y = add_text(y, f"장면: {b2.get('scene_description', '')}", 10, 70)
        
        if "video_brief" in briefs:
            vb = briefs["video_brief"]
            y = add_text(y, "[영상 브리프]", 11, 60)
            y = add_text(y, f"스토리: {vb.get('narrative_arc', '')}", 10, 70)
    
    y -= 15
    
    # ===== 5. 마케팅 자료 =====
    if y < 150:
        y = new_page()
    y = add_heading(y, "5. 마케팅 자료", 16)
    if "marketing_materials" in analysis:
        mk = analysis["marketing_materials"]
        
        if mk.get("slogan"):
            y = add_text(y, f"[슬로건] {mk['slogan']}", 11, 60)
        
        if mk.get("tagline"):
            y = add_text(y, f"[태그라인] {mk['tagline']}", 10, 60)
        
        if mk.get("elevator_pitch"):
            y = add_text(y, f"[엘리베이터 피치] {mk['elevator_pitch']}", 10, 60)
        
        if mk.get("social_media_posts"):
            y = add_text(y, "[소셜미디어 콘텐츠]", 11, 60)
            for idx, post in enumerate(mk["social_media_posts"][:5], 1):
                y = add_text(y, f"{idx}. {post.get('platform', '')}: {post.get('content', '')}", 10, 70)
    
    y -= 15
    
    # ===== 6. 성과 지표 (KPI) =====
    if y < 150:
        y = new_page()
    y = add_heading(y, "6. 성과 지표 (KPI)", 16)
    if "performance_metrics" in analysis:
        metrics = analysis["performance_metrics"]
        
        if metrics.get("kpi_framework"):
            y = add_text(y, "[KPI 프레임워크]", 11, 60)
            for idx, kpi in enumerate(metrics["kpi_framework"][:8], 1):
                y = add_text(y, f"{idx}. {kpi.get('metric', '')}", 10, 70)
                if kpi.get("target_range"):
                    y = add_text(y, f"   목표: {kpi['target_range']}", 9, 75)
        
        if metrics.get("success_criteria"):
            y = add_text(y, "[성공 기준]", 11, 60)
            for sc in metrics["success_criteria"][:5]:
                y = add_text(y, f"• {sc}", 10, 70)
    
    y -= 15
    
    # ===== 7. 이해관계자 관리 =====
    if y < 150:
        y = new_page()
    y = add_heading(y, "7. 이해관계자 관리", 16)
    if "stakeholder_management" in analysis:
        sh = analysis["stakeholder_management"]
        
        if sh.get("stakeholders"):
            y = add_text(y, "[이해관계자 분석]", 11, 60)
            for idx, s in enumerate(sh["stakeholders"][:6], 1):
                y = add_text(y, f"{idx}. {s.get('group', '')}: {s.get('interests', '')}", 10, 70)
        
        if sh.get("objection_handling"):
            y = add_text(y, "[반대 의견 대응]", 11, 60)
            for obj in sh["objection_handling"][:4]:
                y = add_text(y, f"• 반대: {obj.get('objection', '')}", 10, 70)
                y = add_text(y, f"  대응: {obj.get('response', '')}", 9, 75)
    
    y -= 15
    
    # ===== 8. 이미지 프롬프트 =====
    if images:
        if y < 150:
            y = new_page()
        y = add_heading(y, "8. 생성된 이미지", 16)
        
        for idx, img_bytes in enumerate(images[:4], 1):
            if y < 250:
                y = new_page()
            try:
                img = ImageReader(BytesIO(img_bytes))
                c.drawImage(img, 50, y - 200, width=450, height=200, preserveAspectRatio=True)
                y -= 220
                c.setFont(font_name, 10)
                c.drawString(50, y, f"이미지 {idx}")
                y -= 30
            except:
                pass
    
    # ===== 9. 영상 프롬프트 =====
    if video_prompts:
        y = new_page()
        y = add_heading(y, "9. 영상 프롬프트", 16)
        
        for idx, prompt in enumerate(video_prompts[:9], 1):
            if y < 150:
                y = new_page()
            y = add_text(y, f"[영상 {idx}]", 11, 60)
            y = add_text(y, prompt[:600], 9, 70)
            y -= 15
    
    c.save()
    buffer.seek(0)
    return buffer.read()

def create_zip_export(
    policy: Dict[str, Any],
    analysis: Dict[str, Any],
    images: List[bytes] = None,
    video_prompts: List[str] = None,
    pdf_bytes: bytes = None
) -> bytes:
    """모든 자료를 ZIP으로 압축 (PDF 포함)"""
    
    buffer = BytesIO()
    
    with ZipFile(buffer, 'w') as zipf:
        # PDF 보고서 (최우선)
        if pdf_bytes:
            zipf.writestr("정책_보고서_전체.pdf", pdf_bytes)
        
        # 정책 정보
        zipf.writestr("policy_info.json", json.dumps(policy, ensure_ascii=False, indent=2))
        
        # AI 분석 결과
        zipf.writestr("analysis_full.json", json.dumps(analysis, ensure_ascii=False, indent=2))
        
        # 이미지
        if images:
            for idx, img_bytes in enumerate(images, 1):
                zipf.writestr(f"images/image_{idx}.png", img_bytes)
        
        # 영상 프롬프트
        if video_prompts:
            for idx, prompt in enumerate(video_prompts, 1):
                zipf.writestr(f"video_prompts/prompt_{idx}.txt", prompt)
        
        # README
        readme = f"""
정세담 정책 프로그램 - 결과물 패키지

정책 제목: {policy['title']}
생성일: {policy['created_at']}

포함 내용:
- 정책_보고서_전체.pdf: AI 분석 7개 섹션 + 이미지 + 영상 프롬프트 전체 (PDF)
- policy_info.json: 정책 기본 정보
- analysis_full.json: AI 분석 전체 결과 (JSON)
- images/: 생성된 이미지
- video_prompts/: 영상 제작 프롬프트

사용 방법:
1. 정책_보고서_전체.pdf를 열어 전체 내용 확인 (권장)
2. analysis_full.json을 열어 JSON 형태로 확인
3. images 폴더의 이미지 활용
4. video_prompts의 프롬프트를 Sora, Runway, Pika 등에 입력
"""
        zipf.writestr("README.txt", readme)
    
    buffer.seek(0)
    return buffer.read()

# ==================== Streamlit UI ====================

st.set_page_config(
    page_title="정세담 정책 프로그램",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"  # 모바일 최적화: 기본 축소
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    /* 사이드바 화살표 고정 */
    [data-testid="collapsedControl"] {
        position: sticky !important;
        top: 0 !important;
        z-index: 999 !important;
    }
    /* 모바일 최적화 */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.8rem;
        }
        .sub-header {
            font-size: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    defaults = {
        "current_policy_id": None,
        "current_analysis": None,
        "generated_images": [],
        "video_prompts_3styles": [],
        "workflow_step": "기획",
        "show_results": False,
        "selected_category": "",
        "temp_selection": "",
        "active_tab": 0  # 탭 전환용
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()
init_database()

st.markdown('<div class="main-header">🏛️ 정세담 정책 프로그램</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">정책 기획·실행·홍보·성과관리 자동화 시스템</div>', unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.markdown("### 📋 프로세스 단계 (클릭하여 이동)")
    
    step_mapping = {
        "기획": 0,      # 정책 입력 탭
        "실행": 1,      # AI 분석 생성 탭
        "홍보": 2,      # 이미지 생성 탭
        "성과관리": 4   # 결과 및 내보내기 탭
    }
    
    steps = ["기획", "실행", "홍보", "성과관리"]
    current_step_idx = steps.index(st.session_state.workflow_step)
    
    for idx, step in enumerate(steps):
        if idx < current_step_idx:
            if st.button(f"✅ {step}", key=f"step_{step}", use_container_width=True):
                st.session_state.active_tab = step_mapping[step]
                st.rerun()
        elif idx == current_step_idx:
            if st.button(f"▶️ {step} (현재)", key=f"step_{step}", use_container_width=True, type="primary"):
                st.session_state.active_tab = step_mapping[step]
                st.rerun()
        else:
            if st.button(f"⏸️ {step}", key=f"step_{step}", use_container_width=True, disabled=False):
                st.session_state.active_tab = step_mapping[step]
                st.rerun()
    
    st.divider()
    
    st.markdown("### 📅 날짜별 정책 검색")
    
    search_type = st.radio("검색 방식", ["전체 보기", "날짜 선택", "날짜 범위"], horizontal=True)
    
    if search_type == "날짜 선택":
        selected_date = st.date_input("날짜 선택", value=date.today())
        policies = get_policies_by_date(selected_date.strftime("%Y-%m-%d"))
        st.caption(f"{selected_date.strftime('%Y-%m-%d')} 정책 {len(policies)}건")
    elif search_type == "날짜 범위":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("시작", value=date.today())
        with col2:
            end_date = st.date_input("종료", value=date.today())
        policies = get_policies_by_date_range(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )
        st.caption(f"{len(policies)}건 발견")
    else:
        policies = get_all_policies(limit=20)
        st.caption(f"최근 {len(policies)}건")
    
    st.markdown("### 🗂️ 저장된 정책")
    
    if policies:
        for policy in policies:
            with st.expander(f"{policy['title'][:20]}..."):
                st.write(f"📅 {policy['created_at'][:10]}")
                st.write(f"카테고리: {policy['category']}")
                st.write(f"대상: {policy['target_audience']}")
                if st.button("불러오기", key=f"load_{policy['id']}"):
                    st.session_state.current_policy_id = policy['id']
                    contents = get_policy_contents(policy['id'])
                    if contents:
                        for content in contents:
                            if content['content_type'] == 'analysis':
                                st.session_state.current_analysis = content['content_data']
                    
                    media = get_generated_media(policy['id'])
                    st.session_state.generated_images = []
                    
                    for m in media:
                        if m['media_type'] == 'image' and m['media_data']:
                            img = Image.open(BytesIO(m['media_data']))
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": m['media_data'],
                                "brief": "loaded"
                            })
                    
                    st.success(f"✅ 정책 불러오기 완료!")
                    st.rerun()
    else:
        st.info("저장된 정책이 없습니다")
    
    st.divider()
    
    if st.button("🆕 새 정책 시작", use_container_width=True):
        for key in ["current_policy_id", "current_analysis", "generated_images", "video_prompts_3styles", "selected_category", "temp_selection"]:
            st.session_state[key] = [] if "images" in key or "prompts" in key else ("" if "category" in key or "selection" in key else None)
        st.session_state.workflow_step = "기획"
        st.session_state.show_results = False
        st.rerun()

# 메인 탭
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 정책 입력",
    "🤖 AI 분석 생성",
    "🖼️ 이미지 생성",
    "🎬 영상 프롬프트",
    "📊 결과 및 내보내기"
])

with tab1:
    st.markdown("### 1️⃣ 정책 기본 정보 입력")
    
    col1, col2 = st.columns(2)
    
    with col1:
        policy_title = st.text_input(
            "정책 제목 *",
            placeholder="예: 도시 대기질 실시간 관리 정책",
            help="정책의 핵심을 담은 명확한 제목"
        )
        
        # 카테고리 데이터베이스
        category_database = {
            "환경": {
                "대기질": ["미세먼지 저감", "대기오염 관리", "실시간 모니터링", "배출가스 규제", "대기질 예보", "미세먼지 신호등", "클린존 조성", "대기오염 총량제", "배출권 거래", "친환경차 보급", "경유차 저감", "공장 배출 관리"],
                "수질": ["하천 정화", "상수도 개선", "하수처리", "수질 모니터링", "물 절약", "빗물 저장", "하천 생태 복원", "정수장 현대화", "상수도 누수 방지", "지하수 관리", "녹조 관리", "수변 정화"],
                "폐기물": ["쓰레기 감량", "재활용", "음식물쓰레기", "일회용품 규제", "폐기물 분리배출", "자원순환", "재활용센터", "리필스테이션", "플라스틱 줄이기", "생활쓰레기 종량제", "대형폐기물 수거", "불법투기 단속", "재활용 마을", "업사이클링"],
                "에너지": ["신재생에너지", "태양광", "풍력", "에너지 효율화", "절전", "에너지 저장", "스마트그리드", "제로에너지 건축", "에너지 자립마을", "수소에너지", "지열에너지", "LED 조명 교체", "건물 에너지관리", "에너지 진단"],
                "기후변화": ["탄소중립", "온실가스 감축", "기후 적응", "ESG", "탄소배출권", "기후위기 대응", "그린뉴딜", "Net-Zero", "기후변화 교육", "탄소발자국", "기후 취약계층 지원", "폭염 대응", "한파 대비"],
                "녹지": ["도시숲", "공원 조성", "가로수", "옥상녹화", "벽면녹화", "생태공원", "습지 보호", "생물다양성", "도심 숲길", "미세먼지 차단숲", "녹지축 연결", "나무 심기", "정원도시"]
            },
            "교통": {
                "대중교통": ["버스 노선 개편", "지하철 확충", "환승 편의", "요금 정책", "심야버스", "광역버스", "마을버스", "저상버스", "교통카드 통합", "실시간 도착 정보", "BRT", "버스 전용차로", "환승센터", "대중교통 요금 할인", "무료환승"],
                "주차": ["공영주차장", "주차난 해소", "불법주차 단속", "공유주차", "주차장 확충", "거주자우선주차", "공공주차장", "주차요금 정책", "노상주차장", "기계식 주차장", "주차정보 시스템", "주차 공간 공유", "주차 앱", "친환경 주차장"],
                "보행": ["보행자 우선", "보행로 확충", "횡단보도 개선", "무장애 도로", "보행권 보장", "보행환경 개선", "보행섬", "보행신호 연장", "보행 안전", "스쿨존", "실버존", "안전한 통학로", "보행자 전용거리", "보차분리"],
                "자전거": ["자전거 도로", "공유자전거", "자전거 주차장", "안전 인프라", "자전거 도로망", "따릉이", "자전거 수리소", "자전거 거치대", "자전거 보관소", "자전거 교육", "자전거 안전모", "자전거 우선도로"],
                "교통안전": ["교통사고 예방", "과속 단속", "신호위반 단속", "음주운전 단속", "교통약자 보호", "교통안전 교육", "어린이보호구역", "노인보호구역", "교통섬", "과속방지턱", "안전표지판", "신호등 개선"],
                "스마트 교통": ["ITS", "교통정보 시스템", "신호제어 시스템", "교통데이터", "스마트 신호등", "AI 교통관리", "자율주행", "모빌리티", "공유모빌리티", "전기차 충전소", "수소차 충전소", "킥보드 정책"]
            },
            "복지": {
                "노인복지": ["경로당 지원", "돌봄 서비스", "일자리 창출", "건강관리", "치매 예방", "노인 여가", "효도수당", "경로우대", "실버카페", "노인 일자리", "노인 돌봄", "독거노인 지원", "어르신 급식", "노인복지관", "치매 안심센터", "노인 건강검진", "노인 의료지원", "효도관광", "실버타운"],
                "아동복지": ["보육 지원", "놀이터 확충", "아동학대 예방", "방과후 돌봄", "어린이집 확충", "국공립 어린이집", "보육료 지원", "아동수당", "출산장려금", "육아휴직", "놀이터 안전", "아이돌봄 서비스", "아동급식", "아동보호", "아동센터"],
                "청년복지": ["주거 지원", "취업 지원", "청년수당", "창업 지원", "청년주택", "청년 일자리", "청년 수당", "청년 공간", "청년 문화", "청년 활동", "청년 정책", "청년 참여", "대학생 지원", "취업 교육", "구직 지원"],
                "장애인복지": ["장애인 일자리", "편의시설", "이동권 보장", "활동지원", "장애인 복지관", "장애인 수당", "재활치료", "특수교육", "장애인 주차", "저상버스", "장애인 체육", "장애인 문화", "장애인콜택시", "무장애공간"],
                "여성복지": ["여성 일자리", "경력단절 예방", "여성 안전", "여성 폭력 예방", "여성 복지관", "경단녀 재취업", "여성 창업", "여성 건강", "여성 상담", "한부모 지원", "미혼모 지원", "성평등", "여성 친화도시"],
                "저소득층 지원": ["기초생활보장", "긴급복지", "생계지원", "의료지원", "교육지원", "주거지원", "복지사각지대", "푸드뱅크", "물가지원", "에너지바우처", "난방비 지원", "취약계층 보호"]
            },
            "교육": {
                "학교교육": ["교육과정 개선", "학교시설 현대화", "무상급식", "돌봄교실", "학교 안전", "교육환경 개선", "스마트 교실", "교육 기자재", "급식 품질", "학교 공기청정기", "학교 냉난방", "학교 화장실", "학교 체육관", "학교 도서관", "교육 복지"],
                "평생교육": ["성인 교육", "직업훈련", "온라인 강좌", "학습 지원", "평생학습관", "시민대학", "문해교육", "학력인정", "자격증 교육", "재교육", "평생학습도시"],
                "유아교육": ["유치원 확충", "국공립유치원", "유아 교육비", "유아 돌봄", "누리과정", "유아 안전", "유아 체험", "유아 급식", "유아 놀이"],
                "특수교육": ["특수학교", "특수학급", "통합교육", "특수교사", "특수교육 지원", "발달장애 교육", "특수교육 기자재", "치료지원"],
                "방과후·돌봄": ["방과후 학교", "초등돌봄", "아침돌봄", "저녁돌봄", "돌봄교실 확충", "지역아동센터", "다함께돌봄센터", "청소년방과후아카데미"]
            },
            "안전": {
                "재난안전": ["화재 예방", "지진 대비", "태풍 대비", "재난 대응 훈련", "소방시설", "소화기 보급", "화재경보기", "재난문자", "재난대피소", "풍수해 대비", "산사태 예방", "붕괴사고 예방", "가스안전", "전기안전", "승강기 안전", "화학사고 대응", "방사능 대응", "안전문화", "재난안전 교육"],
                "범죄예방": ["CCTV 확충", "안심귀가", "학교폭력 예방", "성범죄 예방", "범죄 취약지역", "방범등", "비상벨", "여성안심택배함", "여성안심귀갓길", "아동안전", "실종아동 예방", "가정폭력 예방", "스토킹 예방", "디지털성범죄 예방"],
                "식품안전": ["식품위생", "위생점검", "학교급식 안전", "식중독 예방", "HACCP", "원산지 표시", "식품검사", "위생등급제", "불량식품 단속"],
                "생활안전": ["어린이놀이터 안전", "승강기 안전", "제품안전", "생활체육 안전", "수상안전", "등산로 안전", "야영장 안전", "레저안전", "시설물 안전점검"],
                "보건안전": ["감염병 예방", "방역", "공중보건", "의료안전", "정신건강", "자살예방", "코로나19 대응", "예방접종", "건강검진"]
            },
            "경제": {
                "일자리": ["일자리 창출", "구직 지원", "직업 훈련", "고용 안정", "청년일자리", "중장년일자리", "여성일자리", "노인일자리", "장애인일자리", "취업박람회", "일자리센터", "고용보험", "직업상담", "취업알선", "워라밸"],
                "창업": ["창업 교육", "자금 지원", "멘토링", "공유 오피스", "창업보육센터", "스타트업", "벤처기업", "소상공인 지원", "예비창업자", "1인창업", "청년창업", "여성창업", "시니어창업"],
                "소상공인": ["소상공인 지원", "전통시장 활성화", "골목상권 보호", "상가임대차 보호", "착한임대인", "배달앱 수수료", "공공배달앱", "제로페이", "소상공인 대출", "컨설팅 지원", "온라인 판로"],
                "지역경제": ["로컬푸드", "지역화폐", "지역상품권", "지역 특산품", "로컬크리에이터", "도시재생", "구도심 활성화", "전통시장", "재래시장", "상권 활성화", "지역 일자리"],
                "기업지원": ["중소기업 지원", "기업 유치", "산업단지", "투자유치", "수출지원", "R&D 지원", "기술개발", "기업 컨설팅", "기업 금융", "기업 교육"]
            },
            "문화": {
                "문화시설": ["문화센터", "도서관", "박물관", "미술관", "공연장", "전시관", "문화공간", "북카페", "작은도서관", "마을도서관", "공공도서관", "문화공원", "문화거리"],
                "문화행사": ["축제", "공연", "전시", "영화제", "음악회", "거리공연", "문화예술제", "지역축제", "전통문화축제", "계절축제", "야간문화행사", "주말공연"],
                "문화예술": ["예술교육", "문화강좌", "예술단체 지원", "예술인 지원", "공공미술", "문화예술 동아리", "아마추어 예술", "생활예술", "시민예술가", "문화동호회"],
                "전통문화": ["문화재 보존", "전통문화 계승", "향토문화", "무형문화재", "한옥마을", "전통시장", "전통음식", "전통공예", "민속놀이", "전통의례"],
                "관광": ["관광지 개발", "관광 홍보", "관광안내", "관광코스", "체험관광", "생태관광", "문화관광", "역사관광", "관광상품", "관광 편의시설"]
            },
            "주거": {
                "공공주택": ["공공임대", "영구임대", "국민임대", "행복주택", "매입임대", "전세임대", "공공분양", "공공주택 확충", "주거복지", "주거급여", "주택바우처"],
                "주거환경": ["노후주택 개선", "주거환경 개선", "빈집정비", "주택리모델링", "슬레이트 제거", "주택 에너지효율", "단열 개선", "보일러 교체", "주거 안전", "주택방역"],
                "청년주거": ["청년주택", "청년임대", "청년전세", "셰어하우스", "대학생 기숙사", "청년 주거비 지원", "청년 월세 지원", "청년 전세자금"],
                "주거취약계층": ["쪽방촌", "고시원", "비닐하우스", "컨테이너", "반지하", "옥탑방", "주거복지센터", "주거상담", "주거비 지원", "긴급주거지원"]
            },
            "건설·도시": {
                "도시계획": ["도시재생", "도심재개발", "뉴타운", "도시 정비", "도시설계", "스마트시티", "친환경도시", "압축도시", "직주근접", "복합용도"],
                "건설": ["토목공사", "도로건설", "교량건설", "터널공사", "하천정비", "제방", "항만", "인프라", "공공시설", "체육시설 건설"],
                "도시미관": ["경관 개선", "간판정비", "불법광고물 정비", "가로환경", "도시디자인", "공공디자인", "색채계획", "야간경관", "조명"],
                "마을만들기": ["주민자치", "마을공동체", "도시재생 뉴딜", "골목길 재생", "마을 주차장", "마을회관", "마을 공동이용시설", "마을 텃밭", "마을 쉼터"]
            },
            "농업·농촌": {
                "농업": ["스마트팜", "친환경농업", "유기농", "도시농업", "주말농장", "텃밭", "농업기술", "농기계", "농업인 교육", "청년농업인", "귀농"],
                "농촌": ["농촌개발", "농촌관광", "농촌체험", "귀촌", "농촌주택", "농촌복지", "농촌 의료", "농촌 교통", "농촌 일자리", "농촌 인구"],
                "유통": ["직거래장터", "농산물 직판장", "로컬푸드", "농협판매장", "온라인 판매", "농산물 수출", "농산물 가공", "6차 산업", "푸드플랜"]
            },
            "보건·의료": {
                "공공의료": ["보건소", "공공병원", "의료취약지역", "공공의료 확충", "응급의료", "119구급", "야간진료", "휴일진료", "순회진료"],
                "건강증진": ["건강검진", "예방접종", "건강교육", "금연", "절주", "영양", "운동", "비만예방", "만성질환 관리", "암검진", "구강검진"],
                "정신건강": ["정신건강 복지센터", "자살예방", "심리상담", "트라우마 치료", "중독 치료", "스트레스 관리", "우울증", "불안장애", "정신건강 교육"],
                "의료지원": ["의료비 지원", "취약계층 의료", "난임 지원", "출산 지원", "영유아 건강", "노인 의료", "장애인 의료", "희귀질환", "중증질환"]
            },
            "디지털·ICT": {
                "스마트도시": ["스마트시티", "IoT", "빅데이터", "AI 활용", "디지털트윈", "5G", "공공와이파이", "디지털 인프라", "통신망"],
                "전자정부": ["전자민원", "온라인 행정", "모바일 앱", "디지털 서비스", "행정정보 공개", "데이터 개방", "공공데이터", "정보화 사업"],
                "디지털 격차 해소": ["디지털 교육", "정보화 교육", "취약계층 정보화", "시니어 IT교육", "디지털 리터러시", "키오스크 교육", "스마트폰 교육"],
                "정보보호": ["개인정보 보호", "사이버보안", "정보보안", "해킹 방지", "피싱 예방", "랜섬웨어 대응", "정보보호 교육"]
            },
            "체육": {
                "생활체육": ["체육시설", "체육교실", "동네체육관", "공공체육시설", "수영장", "헬스장", "테니스장", "축구장", "농구장", "배드민턴장", "체육프로그램", "생활체육클럽"],
                "전문체육": ["선수 육성", "체육 꿈나무", "유망주 발굴", "체육 영재", "엘리트 체육", "전문체육인 지원", "체육대회 개최"],
                "건강체육": ["걷기운동", "등산", "자전거타기", "국민체조", "건강 프로그램", "건강걷기", "트레킹", "마라톤", "산책로"]
            },
            "과학·기술": {
                "R&D": ["연구개발", "기술개발", "신기술", "산학협력", "연구지원", "연구소", "실험실", "기술사업화", "기술이전"],
                "혁신": ["혁신성장", "기술혁신", "산업혁신", "디지털 전환", "그린전환", "미래기술", "첨단기술", "4차산업", "바이오", "나노", "로봇"],
                "과학문화": ["과학관", "과학체험", "과학교육", "과학축제", "메이커스페이스", "과학동아리", "발명교육", "코딩교육"]
            },
            "행정·참여": {
                "주민참여": ["주민자치", "주민참여예산", "마을회의", "주민총회", "공론화", "주민투표", "주민제안", "주민소통", "시민참여"],
                "민원": ["민원처리", "원스톱 민원", "찾아가는 민원", "무인민원발급기", "민원상담", "고충민원", "민원 만족도"],
                "열린행정": ["정보공개", "행정투명성", "시민감사관", "옴부즈만", "청렴도", "반부패", "공익신고", "행정혁신"],
                "소통·홍보": ["시민소통", "정책홍보", "SNS 소통", "언론홍보", "시정소식", "주민설명회", "간담회", "타운홀미팅"]
            }
        }
        
        # 선택 버튼이 눌렸을 때
        if "temp_selection" in st.session_state and st.session_state.temp_selection:
            st.session_state.selected_category = st.session_state.temp_selection
            st.session_state.temp_selection = ""
        
        # 정책 카테고리 입력창
        policy_category = st.text_input(
            "정책 카테고리 *",
            value=st.session_state.selected_category if st.session_state.selected_category else "",
            placeholder="예: 화재, 청년, 주차 등 입력하면 자동완성됩니다",
            help="한 글자씩 입력하면 관련 카테고리가 자동으로 추천됩니다"
        )
        
        # 사용자가 직접 입력하면 업데이트
        if policy_category != st.session_state.selected_category:
            st.session_state.selected_category = policy_category
        
        # 실시간 자동완성 (모바일/PC 분기)
        if policy_category and len(policy_category) > 0:
            autocomplete_suggestions = []
            
            for main_cat, sub_cats in category_database.items():
                for sub_cat, items in sub_cats.items():
                    for item in items:
                        full_path = f"{main_cat} > {sub_cat} > {item}"
                        if policy_category.lower() in full_path.lower():
                            autocomplete_suggestions.append(full_path)
            
            if autocomplete_suggestions:
                st.markdown("##### 💡 자동완성 추천")
                st.caption(f"{len(autocomplete_suggestions)}개 항목 발견 (최대 10개 표시)")
                
                # 자동완성 표시
                for idx, suggestion in enumerate(autocomplete_suggestions[:10]):
                    cols = st.columns([5, 1])
                    with cols[0]:
                        st.markdown(f"✨ {suggestion}")
                    with cols[1]:
                        if st.button("선택", key=f"autocomplete_{idx}", use_container_width=True):
                            st.session_state.temp_selection = suggestion
                            st.rerun()
                
                if len(autocomplete_suggestions) > 10:
                    st.caption(f"+ {len(autocomplete_suggestions) - 10}개 더 있습니다.")
        else:
            # 입력이 없을 때는 도움말만 표시 (모바일 최적화)
            st.caption("💡 카테고리 입력 시 자동완성이 표시됩니다. 또는 아래 전체 카테고리에서 선택하세요.")
        
        # 전체 카테고리 리스트 표시 (expander로)
        with st.expander("📚 전체 카테고리 목록 보기 (클릭하여 선택)"):
            st.caption("원하는 세부 항목을 클릭하면 자동으로 입력됩니다")
            
            for main_cat, sub_cats in category_database.items():
                st.markdown(f"#### {main_cat}")
                for sub_cat, items in sub_cats.items():
                    st.markdown(f"**{sub_cat}**")
                    
                    # 세부 항목마다 선택 버튼
                    for item in items:
                        cols = st.columns([4, 1])
                        with cols[0]:
                            st.write(f"• {item}")
                        with cols[1]:
                            if st.button("선택", key=f"select_full_{main_cat}_{sub_cat}_{item}", use_container_width=True):
                                st.session_state.temp_selection = f"{main_cat} > {sub_cat} > {item}"
                                st.rerun()
                    
                    st.divider()
        
        target_audience = st.selectbox(
            "주요 대상 *",
            options=list(TARGET_AUDIENCES.keys()),
            help="정책의 주요 대상 그룹"
        )
        
        if target_audience in TARGET_AUDIENCES:
            audience_info = TARGET_AUDIENCES[target_audience]
            st.info(f"**톤**: {audience_info['tone']}\n\n**초점**: {audience_info['focus']}")
    
    with col2:
        policy_description = st.text_area(
            "정책 설명 *",
            height=150,
            placeholder="정책의 배경, 목적, 기대 효과 등을 자세히 입력하세요"
        )
        
        keywords = st.text_input(
            "강조 키워드 (쉼표로 구분)",
            placeholder="예: 시민참여, 데이터기반, 지속가능성"
        )
        
        constraints = st.text_area(
            "제약 조건 (선택)",
            height=100,
            placeholder="예: 예산 1억 이내, 3개월 시범운영"
        )
    
    content_package = st.selectbox(
        "콘텐츠 패키지",
        options=list(CONTENT_PACKAGES.keys())
    )
    
    st.info(f"**선택한 패키지 포함 항목**: {', '.join(CONTENT_PACKAGES[content_package])}")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        if st.button("💾 정책 저장", use_container_width=True):
            if not policy_title or not policy_description:
                st.error("정책 제목과 설명은 필수입니다")
            else:
                policy_id = create_policy(
                    title=policy_title,
                    category=policy_category,
                    target_audience=target_audience,
                    description=policy_description
                )
                st.session_state.current_policy_id = policy_id
                st.success(f"✅ 정책이 저장되었습니다 (ID: {policy_id})")
                st.session_state.workflow_step = "실행"
    
    with col2:
        if st.button("🚀 AI 분석 생성", use_container_width=True):
            if not policy_title or not policy_description:
                st.error("정책 제목과 설명은 필수입니다")
            else:
                try:
                    if not st.session_state.current_policy_id:
                        policy_id = create_policy(
                            title=policy_title,
                            category=policy_category,
                            target_audience=target_audience,
                            description=policy_description
                        )
                        st.session_state.current_policy_id = policy_id
                    
                    with st.spinner("AI가 정책을 분석하고 있습니다... (30-60초 소요)"):
                        analysis, raw = generate_policy_analysis(
                            title=policy_title,
                            category=policy_category,
                            target_audience=target_audience,
                            description=policy_description,
                            keywords=keywords,
                            constraints=constraints
                        )
                        
                        if analysis:
                            st.session_state.current_analysis = analysis
                            save_policy_content(
                                st.session_state.current_policy_id,
                                "analysis",
                                analysis
                            )
                            st.success("✅ AI 분석이 완료되었습니다!")
                            st.session_state.show_results = True
                            st.session_state.workflow_step = "홍보"
                            st.balloons()
                        else:
                            st.error(f"AI 분석 생성에 실패했습니다.")
                            
                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")

with tab2:
    st.markdown("### 2️⃣ AI 생성 결과 (전체 분석)")
    
    if st.session_state.current_analysis:
        analysis = st.session_state.current_analysis
        
        # 정책 기획
        with st.expander("📋 정책 기획", expanded=True):
            if "policy_planning" in analysis:
                planning = analysis["policy_planning"]
                st.markdown(f"**목표**: {planning.get('objective', '')}")
                st.markdown(f"**대상 분석**: {planning.get('target_analysis', '')}")
                
                st.markdown("**핵심 전략**:")
                for idx, strategy in enumerate(planning.get("key_strategies", []), 1):
                    st.write(f"{idx}. {strategy}")
                
                st.markdown("**기대 효과**:")
                for outcome in planning.get("expected_outcomes", []):
                    st.write(f"• {outcome}")
                
                if "timeline" in planning:
                    timeline = planning["timeline"]
                    st.markdown("**타임라인**:")
                    st.write(f"- 준비: {timeline.get('preparation', '')}")
                    st.write(f"- 시범운영: {timeline.get('pilot', '')}")
                    st.write(f"- 확대적용: {timeline.get('expansion', '')}")
        
        # 실행 계획
        with st.expander("⚙️ 실행 계획"):
            if "execution_plan" in analysis:
                execution = analysis["execution_plan"]
                
                action_items = execution.get("action_items", [])
                if action_items:
                    st.markdown("**실행 항목**:")
                    for item in action_items:
                        st.markdown(f"""
**{item.get('phase', '')}**
- 실행 내용: {item.get('action', '')}
- 담당: {item.get('responsible', '')}
- 기간: {item.get('timeline', '')}
""")
                
                if "resources_needed" in execution:
                    resources = execution["resources_needed"]
                    st.markdown("**필요 자원**:")
                    st.write(f"- 예산: {resources.get('budget_range', '')}")
                    st.write(f"- 인력: {resources.get('personnel', '')}")
                    st.write(f"- 인프라: {resources.get('infrastructure', '')}")
                
                st.markdown("**리스크 관리**:")
                for risk in execution.get("risk_management", []):
                    st.warning(f"⚠️ {risk.get('risk', '')}\n- 영향: {risk.get('impact', '')}\n- 완화: {risk.get('mitigation', '')}")
        
        # 커뮤니케이션 전략
        with st.expander("📣 커뮤니케이션 전략"):
            if "communication_strategy" in analysis:
                comm = analysis["communication_strategy"]
                
                st.markdown("**핵심 메시지**:")
                for msg in comm.get("key_messages", []):
                    st.write(f"• {msg}")
                
                if "channels" in comm:
                    st.markdown("**채널 전략**:")
                    for channel in comm.get("channels", []):
                        st.write(f"- {channel.get('channel', '')}: {channel.get('content_type', '')} ({channel.get('frequency', '')})")
                
                if "target_specific_messages" in comm:
                    st.markdown("**대상별 메시지**:")
                    target_msgs = comm["target_specific_messages"]
                    for target, msg in target_msgs.items():
                        st.info(f"**{target}**: {msg}")
        
        # 콘텐츠 제작 브리프
        with st.expander("🎨 콘텐츠 제작 브리프"):
            if "content_briefs" in analysis:
                briefs = analysis["content_briefs"]
                
                st.markdown("### 이미지 브리프 1")
                if "image_brief_1" in briefs:
                    brief1 = briefs["image_brief_1"]
                    st.write(f"**컨셉**: {brief1.get('concept', '')}")
                    st.write(f"**장면**: {brief1.get('scene_description', '')}")
                    st.write(f"**스타일**: {brief1.get('visual_style', '')}")
                    st.success(f"**메시지**: {brief1.get('key_message', '')}")
                
                st.markdown("### 이미지 브리프 2")
                if "image_brief_2" in briefs:
                    brief2 = briefs["image_brief_2"]
                    st.write(f"**컨셉**: {brief2.get('concept', '')}")
                    st.write(f"**장면**: {brief2.get('scene_description', '')}")
                    st.write(f"**스타일**: {brief2.get('visual_style', '')}")
                    st.success(f"**메시지**: {brief2.get('key_message', '')}")
                
                st.markdown("### 영상 브리프")
                if "video_brief" in briefs:
                    video = briefs["video_brief"]
                    st.write(f"**길이**: {video.get('duration', '')}")
                    st.write(f"**스토리**: {video.get('narrative_arc', '')}")
                    st.write(f"**스타일 가이드**: {video.get('style_guide', '')}")
                    st.success(f"**CTA**: {video.get('call_to_action', '')}")
        
        # 마케팅 자료
        with st.expander("📝 마케팅 자료"):
            if "marketing_materials" in analysis:
                marketing = analysis["marketing_materials"]
                
                st.markdown(f"### {marketing.get('slogan', '')}")
                st.markdown(f"**태그라인**: {marketing.get('tagline', '')}")
                st.write(marketing.get('elevator_pitch', ''))
                
                if "social_media_posts" in marketing:
                    st.markdown("**소셜미디어 콘텐츠**:")
                    for post in marketing.get("social_media_posts", []):
                        st.info(f"**{post.get('platform', '')}**\n{post.get('content', '')}\n해시태그: {', '.join(post.get('hashtags', []))}")
                
                st.markdown("**FAQ**:")
                for faq in marketing.get("faq", []):
                    with st.expander(faq.get("question", "")):
                        st.write(faq.get("answer", ""))
        
        # 성과 지표 (KPI)
        with st.expander("📈 성과 지표 (KPI)"):
            if "performance_metrics" in analysis:
                metrics = analysis["performance_metrics"]
                
                kpi_framework = metrics.get("kpi_framework", [])
                if kpi_framework:
                    for kpi in kpi_framework:
                        st.markdown(f"""
**{kpi.get('metric', '')}** ({kpi.get('category', '')})
- 측정 방법: {kpi.get('measurement_method', '')}
- 목표 범위: {kpi.get('target_range', '')}
- 데이터 출처: {kpi.get('data_source', '')}
""")
                
                if "success_criteria" in metrics:
                    st.markdown("**성공 기준**:")
                    for criteria in metrics.get("success_criteria", []):
                        st.write(f"✓ {criteria}")
                
                if "monitoring_plan" in metrics:
                    monitoring = metrics["monitoring_plan"]
                    st.markdown("**모니터링 계획**:")
                    st.write(f"- 일간: {monitoring.get('daily', '')}")
                    st.write(f"- 주간: {monitoring.get('weekly', '')}")
                    st.write(f"- 월간: {monitoring.get('monthly', '')}")
        
        # 이해관계자 관리
        with st.expander("🤝 이해관계자 관리"):
            if "stakeholder_management" in analysis:
                stakeholder = analysis["stakeholder_management"]
                
                if "stakeholders" in stakeholder:
                    st.markdown("**이해관계자 분석**:")
                    for sh in stakeholder.get("stakeholders", []):
                        st.markdown(f"""
**{sh.get('group', '')}**
- 관심사: {sh.get('interests', '')}
- 소통 전략: {sh.get('engagement_strategy', '')}
""")
                
                if "objection_handling" in stakeholder:
                    st.markdown("**반대 의견 대응**:")
                    for obj in stakeholder.get("objection_handling", []):
                        st.warning(f"**반대**: {obj.get('objection', '')}\n**대응**: {obj.get('response', '')}")
    
    else:
        st.info("먼저 '정책 입력' 탭에서 정책 정보를 입력하고 AI 분석을 생성해주세요.")

with tab3:
    st.markdown("### 3️⃣ 이미지 자동 생성")
    
    if st.session_state.current_analysis and "content_briefs" in st.session_state.current_analysis:
        briefs = st.session_state.current_analysis["content_briefs"]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            image_size = st.selectbox("이미지 크기", IMAGE_SIZES)
        
        with col2:
            image_quality = st.selectbox("품질", ["standard", "hd"])
        
        with col3:
            num_images = st.number_input("생성 개수", min_value=1, max_value=4, value=2)
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🖼️ 이미지 1 생성", use_container_width=True):
                if "image_brief_1" in briefs:
                    with st.spinner("이미지를 생성하고 있습니다... (20-40초)"):
                        result = generate_policy_image(
                            briefs["image_brief_1"],
                            size=image_size,
                            quality=image_quality
                        )
                        if result:
                            img, img_bytes = result
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": img_bytes,
                                "brief": "image_brief_1"
                            })
                            
                            if st.session_state.current_policy_id:
                                save_generated_media(
                                    st.session_state.current_policy_id,
                                    "image",
                                    img_bytes,
                                    generate_image_prompt(briefs["image_brief_1"]),
                                    {"size": image_size, "quality": image_quality}
                                )
                            
                            st.success("✅ 이미지 1 생성 완료!")
                            st.rerun()
                        else:
                            st.error("이미지 생성에 실패했습니다")
        
        with col2:
            if st.button("🖼️ 이미지 2 생성", use_container_width=True):
                if "image_brief_2" in briefs:
                    with st.spinner("이미지를 생성하고 있습니다... (20-40초)"):
                        result = generate_policy_image(
                            briefs["image_brief_2"],
                            size=image_size,
                            quality=image_quality
                        )
                        if result:
                            img, img_bytes = result
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": img_bytes,
                                "brief": "image_brief_2"
                            })
                            
                            if st.session_state.current_policy_id:
                                save_generated_media(
                                    st.session_state.current_policy_id,
                                    "image",
                                    img_bytes,
                                    generate_image_prompt(briefs["image_brief_2"]),
                                    {"size": image_size, "quality": image_quality}
                                )
                            
                            st.success("✅ 이미지 2 생성 완료!")
                            st.rerun()
                        else:
                            st.error("이미지 생성에 실패했습니다")
        
        st.divider()
        
        if st.session_state.generated_images:
            st.markdown(f"### 생성된 이미지 ({len(st.session_state.generated_images)}장)")
            
            cols = st.columns(2)
            for idx, img_data in enumerate(st.session_state.generated_images):
                with cols[idx % 2]:
                    st.image(img_data["image"], use_column_width=True)
                    st.caption(f"이미지 {idx+1}")
                    
                    buffer = BytesIO(img_data["bytes"])
                    st.download_button(
                        f"💾 이미지 {idx+1} 다운로드",
                        buffer,
                        file_name=f"policy_image_{idx+1}.png",
                        mime="image/png",
                        key=f"download_img_{idx}"
                    )
        else:
            st.info("이미지를 생성하려면 위의 버튼을 클릭하세요")
    
    else:
        st.info("먼저 AI 분석을 생성해주세요")

with tab4:
    st.markdown("### 4️⃣ 영상 프롬프트 생성 (10초 3종 스타일)")
    
    if st.session_state.current_analysis and "content_briefs" in st.session_state.current_analysis:
        briefs = st.session_state.current_analysis["content_briefs"]
        
        if "video_brief" in briefs:
            video_brief = briefs["video_brief"]
            
            st.info("🎬 **10초 영상 3가지 스타일**이 자동 생성됩니다: 다큐멘터리, 시네마틱, 모던 다이내믹")
            
            if st.button("🎬 10초 영상 3종 프롬프트 생성", use_container_width=True, type="primary"):
                with st.spinner("3가지 스타일의 영상 프롬프트 생성 중..."):
                    prompts_3styles = generate_video_prompts_3styles(video_brief)
                    
                    if "video_prompts_3styles" not in st.session_state:
                        st.session_state.video_prompts_3styles = []
                    
                    st.session_state.video_prompts_3styles.append(prompts_3styles)
                    st.success("✅ 10초 영상 3종 프롬프트가 생성되었습니다!")
                    st.balloons()
            
            st.divider()
            
            # 3종 스타일 프롬프트 표시
            if "video_prompts_3styles" in st.session_state and st.session_state.video_prompts_3styles:
                st.markdown("### 📹 생성된 영상 프롬프트")
                
                for set_idx, prompt_set in enumerate(st.session_state.video_prompts_3styles):
                    st.markdown(f"#### 세트 {set_idx + 1}")
                    
                    # 스타일 1: 다큐멘터리
                    with st.expander("🎥 스타일 1: 다큐멘터리 리얼리즘", expanded=True):
                        st.text_area(
                            "프롬프트 (다큐멘터리)",
                            prompt_set["documentary"],
                            height=400,
                            key=f"video_doc_{set_idx}"
                        )
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["documentary"],
                                file_name=f"video_documentary_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_doc_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🎬 Sora", VIDEO_PLATFORMS["Sora"], use_container_width=True)
                        with col3:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col4:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    # 스타일 2: 시네마틱
                    with st.expander("🎬 스타일 2: 시네마틱 드라마", expanded=True):
                        st.text_area(
                            "프롬프트 (시네마틱)",
                            prompt_set["cinematic"],
                            height=400,
                            key=f"video_cine_{set_idx}"
                        )
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["cinematic"],
                                file_name=f"video_cinematic_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_cine_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🎬 Sora", VIDEO_PLATFORMS["Sora"], use_container_width=True)
                        with col3:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col4:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    # 스타일 3: 모던 다이내믹
                    with st.expander("⚡ 스타일 3: 모던 다이내믹", expanded=True):
                        st.text_area(
                            "프롬프트 (모던)",
                            prompt_set["modern_dynamic"],
                            height=400,
                            key=f"video_modern_{set_idx}"
                        )
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["modern_dynamic"],
                                file_name=f"video_modern_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_modern_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🎬 Sora", VIDEO_PLATFORMS["Sora"], use_container_width=True)
                        with col3:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col4:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    st.divider()
            else:
                st.info("위의 '10초 영상 3종 프롬프트 생성' 버튼을 클릭하세요")
            
            st.divider()
            
            st.markdown("### 🎥 영상 제작 플랫폼")
            st.caption("생성된 프롬프트를 아래 플랫폼에서 사용하세요")
            cols = st.columns(len(VIDEO_PLATFORMS))
            for idx, (platform, url) in enumerate(VIDEO_PLATFORMS.items()):
                with cols[idx]:
                    st.link_button(platform, url, use_container_width=True)
        
        else:
            st.info("영상 브리프가 생성되지 않았습니다")
    
    else:
        st.info("먼저 AI 분석을 생성해주세요")

with tab5:
    st.markdown("### 5️⃣ 결과 및 내보내기")
    
    if st.session_state.current_policy_id and st.session_state.current_analysis:
        policy = get_policy(st.session_state.current_policy_id)
        
        st.markdown("#### 정책 정보")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("정책 ID", policy['id'])
        with col2:
            st.metric("카테고리", policy['category'])
        with col3:
            st.metric("대상", policy['target_audience'])
        with col4:
            st.metric("상태", policy['status'])
        
        st.markdown(f"**제목**: {policy['title']}")
        st.markdown(f"**설명**: {policy['description'][:100]}...")
        
        st.divider()
        
        st.markdown("#### 생성된 콘텐츠")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("이미지", f"{len(st.session_state.generated_images)}장")
        with col2:
            video_count = len(st.session_state.video_prompts_3styles)
            st.metric("영상 프롬프트", f"{video_count}세트")
        with col3:
            st.metric("AI 분석", "완료" if st.session_state.current_analysis else "없음")
        
        st.divider()
        
        st.markdown("#### 📥 다운로드")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 PDF 보고서", use_container_width=True):
                with st.spinner("PDF를 생성하고 있습니다..."):
                    # 이미지 바이트 수집
                    image_bytes = [img['bytes'] for img in st.session_state.generated_images]
                    
                    # 영상 프롬프트 텍스트 수집
                    video_texts = []
                    for idx, prompt_set in enumerate(st.session_state.video_prompts_3styles, 1):
                        video_texts.append(f"[세트 {idx} - 다큐멘터리]\n{prompt_set.get('documentary', '')}")
                        video_texts.append(f"[세트 {idx} - 시네마틱]\n{prompt_set.get('cinematic', '')}")
                        video_texts.append(f"[세트 {idx} - 모던 다이내믹]\n{prompt_set.get('modern_dynamic', '')}")
                    
                    pdf_bytes = create_pdf_report(
                        policy, 
                        st.session_state.current_analysis,
                        images=image_bytes if image_bytes else None,
                        video_prompts=video_texts if video_texts else None
                    )
                    st.download_button(
                        "💾 PDF 다운로드",
                        pdf_bytes,
                        file_name=f"policy_report_{policy['id']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        
        with col2:
            if st.button("📦 전체 ZIP", use_container_width=True):
                with st.spinner("ZIP 파일을 생성하고 있습니다..."):
                    image_bytes = [img['bytes'] for img in st.session_state.generated_images]
                    
                    # 영상 프롬프트 3종 모두 텍스트로 변환
                    video_texts = []
                    for idx, prompt_set in enumerate(st.session_state.video_prompts_3styles, 1):
                        video_texts.append(f"[세트 {idx} - 다큐멘터리]\n{prompt_set.get('documentary', '')}")
                        video_texts.append(f"[세트 {idx} - 시네마틱]\n{prompt_set.get('cinematic', '')}")
                        video_texts.append(f"[세트 {idx} - 모던 다이내믹]\n{prompt_set.get('modern_dynamic', '')}")
                    
                    # PDF 먼저 생성
                    pdf_bytes = create_pdf_report(
                        policy, 
                        st.session_state.current_analysis,
                        images=image_bytes if image_bytes else None,
                        video_prompts=video_texts if video_texts else None
                    )
                    
                    # ZIP 생성 (PDF 포함)
                    zip_bytes = create_zip_export(
                        policy,
                        st.session_state.current_analysis,
                        images=image_bytes,
                        video_prompts=video_texts if video_texts else None,
                        pdf_bytes=pdf_bytes
                    )
                    
                    st.download_button(
                        "💾 ZIP 다운로드",
                        zip_bytes,
                        file_name=f"policy_package_{policy['id']}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
    
    else:
        st.info("정책을 생성하고 AI 분석을 완료해주세요")
