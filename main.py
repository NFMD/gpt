#!/usr/bin/env python3
"""
한국 주식 자동매매 프로그램
종가 베팅 전략 기반 자동매매 시스템

사용법:
  python main.py --mode scan         # 시장 스캔만 실행
  python main.py --mode buy          # 종가 베팅 실행
  python main.py --mode sell         # 오전 매도 실행
  python main.py --mode portfolio    # 포트폴리오 확인
  python main.py --mode scheduler    # 자동 스케줄러 실행 (기본값)
"""
import argparse
import sys
from api import KISApi
from trading import TradingEngine
from scheduler import run_scheduler
from config import Config


def main():
    parser = argparse.ArgumentParser(description='한국 주식 자동매매 프로그램')
    parser.add_argument(
        '--mode',
        choices=['scan', 'buy', 'sell', 'portfolio', 'scheduler'],
        default='scheduler',
        help='실행 모드 선택 (기본: scheduler)'
    )

    args = parser.parse_args()

    # API 초기화
    try:
        api = KISApi()
        engine = TradingEngine(api)
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        print("\n💡 .env 파일을 확인하고 API 키를 설정해주세요.")
        sys.exit(1)

    # 모드별 실행
    try:
        if args.mode == 'scan':
            print("🔍 시장 스캔 모드")
            engine.scan_market()

        elif args.mode == 'buy':
            print("💰 종가 베팅 모드")
            engine.execute_closing_bet()

        elif args.mode == 'sell':
            print("💸 오전 매도 모드")
            engine.execute_morning_sell()

        elif args.mode == 'portfolio':
            print("📂 포트폴리오 확인 모드")
            engine.check_portfolio()

        elif args.mode == 'scheduler':
            print("⏰ 자동 스케줄러 모드")
            run_scheduler()

    except KeyboardInterrupt:
        print("\n\n⏹️  프로그램 종료")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
