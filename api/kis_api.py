"""
한국투자증권 KIS API 클라이언트
실시간 시세, 거래대금, 주문 기능을 제공합니다.
"""
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KISApi:
    """한국투자증권 OpenAPI 클라이언트"""

    def __init__(self):
        self.base_url = Config.KIS_BASE_URL
        self.app_key = Config.KIS_APP_KEY
        self.app_secret = Config.KIS_APP_SECRET
        self.account_no = Config.KIS_ACCOUNT_NO
        self.account_code = Config.KIS_ACCOUNT_CODE
        self.access_token = None
        self.token_expires_at = None

    def _get_headers(self, tr_id: str, content_type: str = "application/json") -> Dict:
        """API 요청 헤더 생성"""
        if not self.access_token or datetime.now() >= self.token_expires_at:
            self._issue_token()

        return {
            "content-type": content_type,
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

    def _issue_token(self):
        """액세스 토큰 발급"""
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        try:
            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

            self.access_token = data["access_token"]
            expires_in = int(data["expires_in"])
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

            logger.info("✅ API 토큰 발급 성공")
        except Exception as e:
            logger.error(f"❌ 토큰 발급 실패: {e}")
            raise

    def get_stock_price(self, stock_code: str) -> Optional[Dict]:
        """
        현재가 조회

        Args:
            stock_code: 종목코드 (6자리)

        Returns:
            현재가 정보 딕셔너리
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = self._get_headers("FHKST01010100")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data["rt_cd"] == "0":
                output = data["output"]
                return {
                    "stock_code": stock_code,
                    "stock_name": output["prdt_name"],
                    "current_price": int(output["stck_prpr"]),
                    "change_rate": float(output["prdy_ctrt"]),
                    "trading_volume": int(output["acml_vol"]),
                    "trading_value": int(output["acml_tr_pbmn"]),
                    "high_price": int(output["stck_hgpr"]),
                    "low_price": int(output["stck_lwpr"]),
                }
            else:
                logger.warning(f"⚠️  시세 조회 실패: {data['msg1']}")
                return None

        except Exception as e:
            logger.error(f"❌ 시세 조회 오류 ({stock_code}): {e}")
            return None

    def get_top_gainers(self, count: int = 20) -> List[Dict]:
        """
        등락률 상위 종목 조회

        Args:
            count: 조회할 종목 수

        Returns:
            등락률 상위 종목 리스트
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/volume-rank"
        headers = self._get_headers("FHPST01710000")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20171",
            "fid_input_iscd": "0000",
            "fid_div_cls_code": "0",
            "fid_blng_cls_code": "0",
            "fid_trgt_cls_code": "111111111",
            "fid_trgt_exls_cls_code": "000000",
            "fid_input_price_1": "",
            "fid_input_price_2": "",
            "fid_vol_cnt": "",
            "fid_input_date_1": "",
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data["rt_cd"] == "0":
                stocks = []
                for item in data["output"][:count]:
                    stocks.append({
                        "stock_code": item["mksc_shrn_iscd"],
                        "stock_name": item["hts_kor_isnm"],
                        "current_price": int(item["stck_prpr"]),
                        "change_rate": float(item["prdy_ctrt"]),
                        "trading_volume": int(item["acml_vol"]),
                        "trading_value": int(item["acml_tr_pbmn"]),
                    })
                return stocks
            else:
                logger.warning(f"⚠️  등락률 상위 조회 실패: {data['msg1']}")
                return []

        except Exception as e:
            logger.error(f"❌ 등락률 상위 조회 오류: {e}")
            return []

    def get_minute_price_history(
        self,
        stock_code: str,
        interval: int = 1,
        count: int = 30
    ) -> List[Dict]:
        """
        분봉 데이터 조회 (장중 실시간 분석용)

        Args:
            stock_code: 종목코드
            interval: 분봉 간격 (1, 3, 5, 10, 30, 60)
            count: 조회할 봉 개수

        Returns:
            분봉 데이터 리스트 (최신순)
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        headers = self._get_headers("FHKST03010200")

        # 분봉 구분 코드 매핑
        interval_map = {1: "0", 3: "1", 5: "2", 10: "3", 30: "4", 60: "5"}
        fid_etc_cls_code = interval_map.get(interval, "0")

        params = {
            "fid_etc_cls_code": fid_etc_cls_code,
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
            "fid_input_hour_1": "",  # 공백이면 현재 시간 기준
            "fid_pw_data_incu_yn": "Y",  # 과거 데이터 포함
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data["rt_cd"] == "0":
                minute_data = []
                for item in data["output2"][:count]:
                    minute_data.append({
                        "time": item["stck_bsop_date"] + item["stck_cntg_hour"],  # YYYYMMDDHHMMss
                        "open": int(item["stck_oprc"]),
                        "high": int(item["stck_hgpr"]),
                        "low": int(item["stck_lwpr"]),
                        "close": int(item["stck_prpr"]),
                        "volume": int(item["cntg_vol"]),
                        "trading_value": int(item["acml_tr_pbmn"]),  # 누적 거래대금
                    })
                return minute_data
            else:
                logger.warning(f"⚠️  분봉 조회 실패: {data.get('msg1', 'Unknown error')}")
                return []

        except Exception as e:
            logger.error(f"❌ 분봉 조회 오류 ({stock_code}): {e}")
            return []

    def get_daily_price_history(self, stock_code: str, days: int = 20) -> List[Dict]:
        """
        일봉 데이터 조회 (기술적 분석용)

        Args:
            stock_code: 종목코드
            days: 조회 기간 (일)

        Returns:
            일봉 데이터 리스트
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
        headers = self._get_headers("FHKST01010400")

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
            "fid_org_adj_prc": "0",
            "fid_period_div_code": "D",
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data["rt_cd"] == "0":
                price_data = []
                for item in data["output"][:days]:
                    price_data.append({
                        "date": item["stck_bsop_date"],
                        "open": int(item["stck_oprc"]),
                        "high": int(item["stck_hgpr"]),
                        "low": int(item["stck_lwpr"]),
                        "close": int(item["stck_clpr"]),
                        "volume": int(item["acml_vol"]),
                    })
                return price_data
            else:
                logger.warning(f"⚠️  일봉 조회 실패: {data['msg1']}")
                return []

        except Exception as e:
            logger.error(f"❌ 일봉 조회 오류 ({stock_code}): {e}")
            return []

    def get_investor_trading(self, stock_code: str) -> Optional[Dict]:
        """
        투자자별 매매동향 조회 (외국인/기관 매수세)

        Args:
            stock_code: 종목코드

        Returns:
            투자자별 매매 정보
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-investor"
        headers = self._get_headers("FHKST01010900")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code,
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data["rt_cd"] == "0" and len(data["output"]) > 0:
                output = data["output"][0]
                return {
                    "stock_code": stock_code,
                    "foreign_net_buy": int(output.get("frgn_ntby_qty", 0)),
                    "institution_net_buy": int(output.get("orgn_ntby_qty", 0)),
                }
            else:
                return {
                    "stock_code": stock_code,
                    "foreign_net_buy": 0,
                    "institution_net_buy": 0,
                }

        except Exception as e:
            logger.error(f"❌ 투자자 매매동향 조회 오류 ({stock_code}): {e}")
            return None

    def place_order(self, stock_code: str, quantity: int, price: int, order_type: str = "buy") -> bool:
        """
        주문 실행 (매수/매도)

        Args:
            stock_code: 종목코드
            quantity: 수량
            price: 가격 (0이면 시장가)
            order_type: 'buy' 또는 'sell'

        Returns:
            주문 성공 여부
        """
        if not Config.TRADING_ENABLED:
            logger.info(f"🔵 [모의] {order_type.upper()} 주문: {stock_code} {quantity}주 @ {price}원")
            return True

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"

        # 매수/매도 구분
        tr_id = "TTTC0802U" if order_type == "buy" else "TTTC0801U"
        headers = self._get_headers(tr_id)

        body = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_code,
            "PDNO": stock_code,
            "ORD_DVSN": "01" if price > 0 else "01",  # 01:지정가, 01:시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price),
        }

        try:
            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

            if data["rt_cd"] == "0":
                logger.info(f"✅ {order_type.upper()} 주문 성공: {stock_code} {quantity}주")
                return True
            else:
                logger.error(f"❌ 주문 실패: {data['msg1']}")
                return False

        except Exception as e:
            logger.error(f"❌ 주문 오류: {e}")
            return False

    def get_balance(self) -> Dict:
        """
        계좌 잔고 조회

        Returns:
            보유 종목 및 현금 정보
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        headers = self._get_headers("TTTC8434R")
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data["rt_cd"] == "0":
                holdings = []
                for item in data["output1"]:
                    if int(item["hldg_qty"]) > 0:
                        holdings.append({
                            "stock_code": item["pdno"],
                            "stock_name": item["prdt_name"],
                            "quantity": int(item["hldg_qty"]),
                            "avg_price": int(float(item["pchs_avg_pric"])),
                            "current_price": int(item["prpr"]),
                            "eval_profit_loss": int(item["evlu_pfls_amt"]),
                            "profit_rate": float(item["evlu_pfls_rt"]),
                        })

                cash = int(data["output2"][0]["dnca_tot_amt"]) if data["output2"] else 0

                return {
                    "holdings": holdings,
                    "cash": cash,
                }
            else:
                logger.warning(f"⚠️  잔고 조회 실패: {data['msg1']}")
                return {"holdings": [], "cash": 0}

        except Exception as e:
            logger.error(f"❌ 잔고 조회 오류: {e}")
            return {"holdings": [], "cash": 0}
