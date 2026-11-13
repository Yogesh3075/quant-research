"""Rebuild the two Yahoo Finance inputs of the original scan (they are not committed).

  data/original/Nifty500_10Yr_Historical.csv  adjusted daily closes, one column per ticker
  data/original/Nifty500_with_Sectors.csv     SEM_TRADING_SYMBOL, Sector

Only the hard-coded F&O tickers are downloaded, because the scan filters to them anyway. Yahoo
revises its adjustments, so a rebuild is close to, but not identical with, the original data.
"""

from __future__ import annotations

import logging

import pandas as pd

from pairs.original.scan import APPROVED_FNO_TICKERS, ORIGINAL_DATA, PRICES_CSV, SECTORS_CSV

logger = logging.getLogger(__name__)

START = "2016-01-01"
END = "2026-04-16"  # yfinance's end date is exclusive: data up to 2026-04-15


def build_yahoo_data() -> None:
    """Download prices and sectors for the F&O tickers from Yahoo Finance."""
    import yfinance as yf  # only needed for this download

    ORIGINAL_DATA.mkdir(parents=True, exist_ok=True)
    tickers = sorted(APPROVED_FNO_TICKERS)
    logger.info("Downloading %d tickers from %s to %s", len(tickers), START, END)
    prices = yf.download(tickers, start=START, end=END, auto_adjust=True, progress=False)["Close"]
    prices = prices.dropna(axis=1, how="all")
    prices.index.name = "Date"
    prices.to_csv(PRICES_CSV)
    logger.info("Saved prices for %d tickers, %d days.", prices.shape[1], prices.shape[0])

    rows = []
    for ticker in prices.columns:
        try:
            sector = yf.Ticker(ticker).info.get("sector")
        except Exception as e:  # Yahoo's info endpoint fails for renamed or delisted symbols
            logger.warning("No sector for %s: %s", ticker, e)
            sector = None
        if sector:
            rows.append({"SEM_TRADING_SYMBOL": ticker.replace(".NS", ""), "Sector": sector})
    pd.DataFrame(rows).to_csv(SECTORS_CSV, index=False)
    logger.info("Saved sectors for %d tickers.", len(rows))
