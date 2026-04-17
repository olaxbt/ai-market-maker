# AI Market Maker - 한국어 가이드

## 빠른 시작

### 설치 방법

#### 방법 1: OpenClaw에서 설치
```bash
# OpenClaw 터미널에서
claw install https://github.com/olaxbt/ai-market-maker

# 또는 로컬 설치
git clone https://github.com/olaxbt/ai-market-maker.git
cd ai-market-maker
claw skill install ./openclaw
```

#### 방법 2: 수동 실행
```bash
# 설치 확인
./openclaw/scripts/verify_installation.sh

# 페이퍼 트레이딩
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT

# 백테스팅
python3 openclaw/scripts/claw_runner.py --backtest --symbols BTC/USDT --steps 100
```

## 주요 기능

### 1. 페이퍼 트레이딩 모드
```bash
# 기본 사용법
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT

# 여러 심볼 모니터링
python3 openclaw/scripts/claw_runner.py --paper --ticker "BTC/USDT,ETH/USDT,SOL/USDT"

# 사용자 정의 간격 (초)
export STRATEGY_INTERVAL_SEC=300
python3 openclaw/scripts/claw_runner.py --paper
```

### 2. 백테스팅 모드
```bash
# 빠른 백테스트
python3 openclaw/scripts/claw_runner.py --backtest --symbols BTC/USDT --steps 50

# 다중 심볼 백테스트
python3 openclaw/scripts/claw_runner.py --backtest --symbols "BTC/USDT,ETH/USDT" --steps 100

# 전체 역사적 평가
python3 -m backtest.run_historical_eval --suite daily --max-windows 3
```

### 3. 설치 확인 모드
```bash
# 완전한 확인
python3 openclaw/scripts/claw_runner.py --verify

# 또는 쉘 스크립트 사용
./openclaw/scripts/verify_installation.sh
```

## 설정 가이드

### 환경 변수 설정
```bash
# 예제 설정 복사
cp .env.example .env

# .env 파일 편집
nano .env
```

#### 주요 설정 항목:
```env
# Nexus API (데모 키 포함)
NEXUS_API_KEY=4Qbp6biPAKPS1gOksAySOlqK
NEXUS_DISABLE=0

# Binance 테스트넷 (선택사항)
BINANCE_API_KEY=your_testnet_key
BINANCE_API_SECRET=your_testnet_secret

# OpenAI (선택사항, LLM 기능 활성화)
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini

# 전략 설정
AIMM_DESK_STRATEGY_PRESET=default
STRATEGY_INTERVAL_SEC=180
```

## 문제 해결

### 문제 1: TA-Lib 설치 실패
```bash
# OpenClaw 환경에서는 Conda 추천
conda install -y ta-lib -c conda-forge

# 또는 시스템 패키지 관리자 사용
sudo apt-get install -y ta-lib  # Ubuntu/Debian
brew install ta-lib            # macOS
```

### 문제 2: 모듈 임포트 오류
```bash
# 개발 모드 설치
pip install -e .

# 또는 Python 경로 수동 추가
export PYTHONPATH=/path/to/ai-market-maker/src:$PYTHONPATH
```

### 문제 3: Nexus API 속도 제한
```
⚠️ 데모 키 사용 시 속도 제한 발생 가능
해결책:
1. 자신의 Nexus API 키 사용
2. 요청 빈도 감소
3. 로컬 캐싱 활성화
```

### 문제 4: 의존성 누락
```bash
# 모든 의존성 설치
pip install -r requirements.txt

# 또는 uv 사용
uv sync --extra dev
```

## 고급 기능

### 1. 사용자 정의 에이전트 구성
```python
# custom_agent.py 생성
from src.agents.base_agent import BaseAgent

class CustomTradingAgent(BaseAgent):
    def process(self, context):
        # 사용자 정의 트레이딩 로직
        return {"signal": "BUY", "confidence": 0.8}
```

### 2. 데이터 소스 확장
```python
# 새로운 데이터 소스 추가
from src.tools.data_fetcher import DataFetcher

class CustomDataFetcher(DataFetcher):
    async def fetch_custom_data(self, symbol):
        # 사용자 정의 데이터 가져오기 로직
        return {"price": 50000, "volume": 1000}
```

### 3. 위험 규칙 사용자 정의
`config/policy.default.json`의 `policy` 부분 편집:
```json
{
  "policy": {
    "stop_loss_pct": 0.03,
    "take_profit_pct": 0.08,
    "max_leverage": 4,
    "min_confidence_directional": 0.45
  }
}
```

## 성능 최적화

### 1. 캐싱 활성화
- 로컬 OHLCV 캐시로 API 호출 감소
- `data/ohlcv` 디렉토리 사용

### 2. 간격 조정
- `STRATEGY_INTERVAL_SEC` 증가로 리소스 사용 감소
- 실시간 모니터링 vs 배치 처리 균형

### 3. 리소스 모니터링
- 메모리/CPU 사용량 확인
- 제한된 환경에서의 성능 최적화

## 아키텍처 개요

### 7개 전문 트레이딩 데스크
1. **마켓 스캔** - 새로운 상장, 모멘텀, 유니버스 커버리지
2. **기술적 TA 엔진** - 패턴 인식, MACD, 지표
3. **통계적 알파 엔진** - 팩터 및 교차 섹션 신호
4. **감정 및 내러티브** - 뉴스, 소매 열기, 고래 행동
5. **위험 관리** - 포지션 사이징, 변동성 기반 제한
6. **포트폴리오 관리** - 다중 자산 할당 및 제안 생성
7. **위험 가드** - 실행 전 하드 거부 계층

### LangGraph 오케스트레이션
- 복잡한 의사 결정 흐름
- 완전한 추적성 및 추론 로그
- 표준화된 에이전트 인터페이스

## 지원 및 자료

### 공식 자료
- GitHub: https://github.com/olaxbt/ai-market-maker
- 문서: https://github.com/olaxbt/ai-market-maker/docs
- 이슈 트래커: https://github.com/olaxbt/ai-market-maker/issues

### 문서
- `docs/` 디렉토리: 상세한 아키텍처 문서
- `openclaw/examples/`: 사용 예제
- 정책 스키마: `docs/policy-schema.md`

---

**🚀 기관급 트레이딩 전략을 경험할 준비가 되셨나요?**

```bash
# 마지막 단계: 트레이딩 시작!
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT
```