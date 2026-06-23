#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BitgetFetcher 测试脚本 - 合约接口测试

用法:
    python scripts/test_bitget_fetcher.py

前提条件:
    1. 安装依赖: pip install requests tenacity
    2. 设置代理(可选): export http_proxy=http://127.0.0.1:7897
"""

import sys
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test_bitget")

# 测试用例
TEST_SYMBOLS = [
    "SPCXUSDT",   # SPCX
]

# BitGet API 基础地址
BITGET_API_BASE = "https://api.bitget.com"


def test_bitget_api():
    """测试 BitGet SPCXUSDT 合约 API"""
    try:
        import requests
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
    except ImportError as e:
        logger.error(f"缺少依赖: {e}")
        logger.info("请运行: pip install requests tenacity")
        return False

    REQUEST_TIMEOUT = 10

    TRANSIENT_EXCEPTIONS = (
        requests.exceptions.SSLError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
    )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _get_with_retry(url, params=None):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        return requests.get(url, headers=headers, params=params or {}, timeout=REQUEST_TIMEOUT)

    results = {}

    for symbol in TEST_SYMBOLS:
        logger.info(f"\n{'='*60}")
        logger.info(f"测试交易对: {symbol}")
        logger.info(f"{'='*60}")

        # 1. 测试实时行情 API (v2 mix ticker)
        logger.info(f"[{symbol}] 测试实时行情 API (mix ticker)...")
        try:
            url = f"{BITGET_API_BASE}/api/v2/mix/market/ticker"
            params = {
                "symbol": symbol,
                "productType": "usdt-futures",
            }
            resp = _get_with_retry(url, params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == "00000" and data.get("data"):
                ticker_list = data["data"]
                if ticker_list:
                    ticker = ticker_list[0]
                    logger.info(f"[{symbol}] ✓ 实时行情成功")
                    logger.info(f"    最新价: {ticker.get('lastPr', 'N/A')}")
                    logger.info(f"    24h涨跌%: {ticker.get('change24h', 'N/A')}")
                    logger.info(f"    24h成交量(base): {ticker.get('baseVolume', 'N/A')}")
                    logger.info(f"    24h成交额(quote): {ticker.get('quoteVolume', 'N/A')}")
                    logger.info(f"    24h最高: {ticker.get('high24h', 'N/A')}")
                    logger.info(f"    24h最低: {ticker.get('low24h', 'N/A')}")
                    logger.info(f"    标记价格: {ticker.get('markPrice', 'N/A')}")
                    logger.info(f"    指数价格: {ticker.get('indexPrice', 'N/A')}")
                    results[symbol] = {"realtime": "OK", "ticker": ticker}
                else:
                    logger.warning(f"[{symbol}] 实时行情返回空数据")
                    results[symbol] = {"realtime": "EMPTY"}
            else:
                logger.warning(f"[{symbol}] 实时行情返回异常: {data}")
                results[symbol] = {"realtime": "FAIL", "error": data.get("msg", "Unknown")}
        except Exception as e:
            logger.error(f"[{symbol}] 实时行情失败: {e}")
            results[symbol] = {"realtime": "ERROR", "error": str(e)}

        # 2. 测试 K 线 API (v2 mix candles - 默认100条)
        logger.info(f"[{symbol}] 测试 K 线 API (mix candles, 默认100条)...")
        try:
            url = f"{BITGET_API_BASE}/api/v2/mix/market/candles"
            params = {
                "symbol": symbol,
                "productType": "usdt-futures",
                "granularity": "1D",
                "limit": "100",
            }
            resp = _get_with_retry(url, params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == "00000" and data.get("data"):
                candles = data["data"]
                logger.info(f"[{symbol}] ✓ K线成功, 获取 {len(candles)} 条数据")
                if candles:
                    logger.info(f"[{symbol}] 最新 3 条 K 线:")
                    for i, candle in enumerate(candles[:3]):
                        # 格式: [timestamp, open, high, low, close, base_volume, quote_volume]
                        ts = int(candle[0])
                        date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                        logger.info(f"    {i+1}. {date_str} | 开:{candle[1]} 高:{candle[2]} 低:{candle[3]} 收:{candle[4]} | 量:{candle[5]}")
                    results[symbol]["candles"] = "OK"
                    results[symbol]["candle_count"] = len(candles)
                else:
                    results[symbol]["candles"] = "EMPTY"
            else:
                logger.warning(f"[{symbol}] K线返回异常: {data}")
                results[symbol]["candles"] = "FAIL"
        except Exception as e:
            logger.error(f"[{symbol}] K线失败: {e}")
            results[symbol]["candles"] = "ERROR"

        # 3. 测试历史 K 线 API (v2 mix history-candles - 最大200条)
        logger.info(f"[{symbol}] 测试历史 K 线 API (history-candles, 最大200条)...")
        try:
            url = f"{BITGET_API_BASE}/api/v2/mix/market/history-candles"
            end_ts = int(datetime.now().timestamp() * 1000)
            start_ts = end_ts - (90 * 24 * 60 * 60 * 1000)  # 90 天前

            params = {
                "symbol": symbol,
                "productType": "usdt-futures",
                "granularity": "1D",
                "startTime": str(start_ts),
                "endTime": str(end_ts),
                "limit": "200",
            }
            resp = _get_with_retry(url, params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == "00000" and data.get("data"):
                candles = data["data"]
                logger.info(f"[{symbol}] ✓ 历史K线成功, 获取 {len(candles)} 条数据")
                if candles:
                    logger.info(f"[{symbol}] 最新 3 条 K 线:")
                    for i, candle in enumerate(candles[:3]):
                        ts = int(candle[0])
                        date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                        logger.info(f"    {i+1}. {date_str} | 开:{candle[1]} 高:{candle[2]} 低:{candle[3]} 收:{candle[4]} | 量:{candle[5]}")
                    results[symbol]["history_candles"] = "OK"
                    results[symbol]["history_count"] = len(candles)
                else:
                    results[symbol]["history_candles"] = "EMPTY"
            else:
                logger.warning(f"[{symbol}] 历史K线返回异常: {data}")
                results[symbol]["history_candles"] = "FAIL"
        except Exception as e:
            logger.error(f"[{symbol}] 历史K线失败: {e}")
            results[symbol]["history_candles"] = "ERROR"

    # 汇总
    logger.info(f"\n{'='*60}")
    logger.info("测试结果汇总")
    logger.info(f"{'='*60}")
    for symbol, result in results.items():
        status = "✓" if result.get("realtime") == "OK" and result.get("candles") == "OK" else "✗"
        logger.info(f"{status} {symbol}: realtime={result.get('realtime')}, "
                    f"candles={result.get('candles')}({result.get('candle_count', 0)}), "
                    f"history={result.get('history_candles')}({result.get('history_count', 0)})")

    return all(r.get("realtime") == "OK" and r.get("candles") == "OK" for r in results.values())


if __name__ == "__main__":
    success = test_bitget_api()
    sys.exit(0 if success else 1)
