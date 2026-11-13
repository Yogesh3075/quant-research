"""The original F&O pairs scan, with the audit's two fixes (in-sample selection, two-leg costs).

Filters to a hard-coded list of today's F&O stocks (survivorship-biased, documented), searches
same-sector pairs by correlation and Engle-Granger on data before SPLIT_DATE, and reports
in-sample and out-of-sample KPIs of the rolling-OLS z-score backtest.
"""

from __future__ import annotations

import logging
import warnings

import pandas as pd
from statsmodels.tsa.stattools import coint

from pairs.original.backtest import kpis, run_stat_arb_backtest
from pairs.universe import DATA_DIR, RESULTS_DIR

logger = logging.getLogger(__name__)

ORIGINAL_DATA = DATA_DIR / "original"
PRICES_CSV = ORIGINAL_DATA / "Nifty500_10Yr_Historical.csv"
SECTORS_CSV = ORIGINAL_DATA / "Nifty500_with_Sectors.csv"
CORR_THRESHOLD = 0.80  # minimum Pearson correlation of prices
COINT_THRESHOLD = 0.05  # maximum Engle-Granger p-value
MIN_HISTORY = 0.8  # keep tickers with prices on at least 80% of days
MIN_IN_SAMPLE_DAYS = 252
# pairs are chosen on data before SPLIT_DATE only; later data is out of sample
SPLIT_DATE = "2023-01-01"
HOLY_GRAIL = {"is_sharpe": 1.5, "is_max_dd": -15.0, "is_trades": 20}

# today's NSE F&O list as hard-coded in the original code
APPROVED_FNO_TICKERS = {
    "AARTIIND.NS", "ABB.NS", "ABBOTINDIA.NS", "ABCAPITAL.NS", "ABFRL.NS", "ACC.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "ALKEM.NS", "AMBUJACEM.NS", "APOLLOHOSP.NS",
    "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS", "ATUL.NS", "AUBANK.NS",
    "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS",
    "BALKRISIND.NS", "BALRAMCHIN.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BATAINDIA.NS",
    "BEL.NS", "BERGEPAINT.NS", "BHARATFORG.NS", "BHARTIARTL.NS", "BHEL.NS", "BIOCON.NS",
    "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "CANBK.NS", "CANFINHOME.NS", "CHAMBLFERT.NS",
    "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS", "CONCOR.NS",
    "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS", "DABUR.NS", "DALBHARAT.NS",
    "DEEPAKNTR.NS", "DIVISLAB.NS", "DIXON.NS", "DLF.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "GAIL.NS", "GLENMARK.NS", "GMRINFRA.NS",
    "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS", "GRASIM.NS", "GUJGASLTD.NS", "HAL.NS",
    "HAVELLS.NS", "HCLTECH.NS", "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "HINDCOPPER.NS", "HINDPETRO.NS", "HINDUNILVR.NS", "ICICIBANK.NS",
    "ICICIGI.NS", "ICICIPRULI.NS", "IDEA.NS", "IDFCFIRSTB.NS", "IEX.NS", "IGL.NS",
    "INDHOTEL.NS", "INDIAMART.NS", "INDIGO.NS", "INDUSINDBK.NS", "INDUSTOWER.NS", "INFY.NS",
    "IOC.NS", "IPCALAB.NS", "IRCTC.NS", "ITC.NS", "JINDALSTEL.NS", "JKCEMENT.NS",
    "JSWSTEEL.NS", "JUBLFOOD.NS", "KOTAKBANK.NS", "LALPATHLAB.NS", "LAURUSLABS.NS",
    "LICHSGFIN.NS", "LT.NS", "LTIM.NS", "LTTS.NS", "LUPIN.NS", "M&M.NS", "M&MFIN.NS",
    "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", "MCX.NS", "METROPOLIS.NS", "MFSL.NS",
    "MGL.NS", "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS",
    "NAUKRI.NS", "NAVINFLUOR.NS", "NESTLEIND.NS", "NMDC.NS", "NTPC.NS", "OBEROIRLTY.NS",
    "OFSS.NS", "ONGC.NS", "PAGEIND.NS", "PEL.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS",
    "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "POLYCAB.NS", "POWERGRID.NS", "PVRINOX.NS",
    "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", "SBICARD.NS",
    "SBILIFE.NS", "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SIEMENS.NS", "SRF.NS",
    "SUNPHARMA.NS", "SUNTV.NS", "SYNGENE.NS", "TATACHEM.NS", "TATACOMM.NS", "TATACONSUM.NS",
    "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS",
    "TORNTPHARM.NS", "TRENT.NS", "TVSMOTOR.NS", "UBL.NS", "ULTRACEMCO.NS", "UPL.NS",
    "VEDL.NS", "VOLTAS.NS", "WIPRO.NS", "ZEEL.NS", "ZYDUSLIFE.NS",
}  # fmt: skip
REPORT_COLUMNS = [
    "Sector", "Asset Y", "Asset X", "IS Sharpe", "IS MaxDD (%)", "IS Total Trades",
    "OOS Sharpe", "OOS Sharpe (daily)", "OOS MaxDD (%)", "OOS Total Trades",
]  # fmt: skip


def load_universe() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Yahoo prices and sectors, restricted to F&O tickers with enough history."""
    if not PRICES_CSV.exists():
        raise SystemExit(f"{PRICES_CSV} not found. Run: python scripts/original.py data")
    prices = pd.read_csv(PRICES_CSV, index_col="Date", parse_dates=True)
    prices = prices.ffill().dropna(axis=1, thresh=len(prices) * MIN_HISTORY)

    sectors = pd.read_csv(SECTORS_CSV)
    sectors["Ticker"] = sectors["SEM_TRADING_SYMBOL"].astype(str) + ".NS"
    valid = [t for t in sectors["Ticker"] if t in prices.columns and t in APPROVED_FNO_TICKERS]
    prices = prices[valid]
    sectors = sectors[sectors["Ticker"].isin(valid)]
    logger.info("Universe filtered down to %d highly liquid F&O stocks.", len(valid))
    return prices, sectors


def run_scan() -> pd.DataFrame | None:
    """Select pairs in sample, backtest them and write results/FnO_StatArb_Report.csv."""
    warnings.filterwarnings("ignore")  # statsmodels warns on near-collinear price pairs
    prices, sectors = load_universe()
    RESULTS_DIR.mkdir(exist_ok=True)
    rows, daily_returns = [], {}
    n_pairs_sector, n_pairs_corr = 0, 0

    for sector, group in sectors.groupby("Sector"):
        tickers = group["Ticker"].tolist()
        if len(tickers) < 2:
            continue
        sector_prices = prices[tickers].dropna()
        in_sample = sector_prices[sector_prices.index < SPLIT_DATE]
        if len(in_sample) < MIN_IN_SAMPLE_DAYS:
            continue
        logger.info("Analysing sector %s (%d stocks)", sector, len(tickers))

        corr = in_sample.corr()
        candidates = [
            (tickers[i], tickers[j])
            for i in range(len(tickers))
            for j in range(i + 1, len(tickers))
            if corr.iloc[i, j] >= CORR_THRESHOLD
        ]
        n_pairs_sector += len(tickers) * (len(tickers) - 1) // 2
        n_pairs_corr += len(candidates)

        for y_sym, x_sym in candidates:
            # The original skipped any pair whose test or backtest raised (e.g. an empty
            # out-of-sample slice); kept so the reported pair set reproduces, but logged.
            try:
                _, pvalue, _ = coint(in_sample[y_sym], in_sample[x_sym])
                if pvalue > COINT_THRESHOLD:
                    continue
                # the rolling beta and z-score are causal, so run on the full series and score
                # the in-sample and out-of-sample days separately
                net_ret, trades = run_stat_arb_backtest(sector_prices[y_sym], sector_prices[x_sym])
                is_days = net_ret.index < SPLIT_DATE
                row = {
                    "Sector": sector,
                    "Asset Y": y_sym,
                    "Asset X": x_sym,
                    "Correlation (IS)": round(corr.loc[y_sym, x_sym], 3),
                    "Coint P-Value (IS)": round(pvalue, 4),
                }
                for k, v in kpis(net_ret[is_days], trades[is_days]).items():
                    row["IS " + k] = v
                for k, v in kpis(net_ret[~is_days], trades[~is_days]).items():
                    row["OOS " + k] = v
            except Exception as e:
                logger.warning("Skipping %s|%s: %s: %s", y_sym, x_sym, type(e).__name__, e)
                continue
            rows.append(row)
            daily_returns[f"{y_sym}|{x_sym}"] = net_ret

    logger.info(
        "Trial count: %d intra-sector pairs, %d passed correlation, %d passed cointegration and "
        "were backtested.",
        n_pairs_sector, n_pairs_corr, len(rows),
    )  # fmt: skip
    if not rows:
        logger.warning(
            "No cointegrated pairs found meeting the correlation and cointegration thresholds."
        )
        return None

    report = pd.DataFrame(rows).sort_values(by=["Sector", "IS Sharpe"], ascending=[True, False])
    report.to_csv(RESULTS_DIR / "FnO_StatArb_Report.csv", index=False)
    # not committed (2 MB); the audit reads it
    pd.DataFrame(daily_returns).to_csv(RESULTS_DIR / "daily_net_returns.csv")
    logger.info("Saved %d pairs to results/FnO_StatArb_Report.csv", len(report))

    # the original "Holy Grail" rule, applied to in-sample results only
    holy_grail = report[
        (report["IS Sharpe"] > HOLY_GRAIL["is_sharpe"])
        & (report["IS MaxDD (%)"] >= HOLY_GRAIL["is_max_dd"])
        & (report["IS Total Trades"] >= HOLY_GRAIL["is_trades"])
    ]
    if holy_grail.empty:
        logger.info(
            "Holy Grail rule (IS Sharpe > 1.5, IS MaxDD > -15%%, IS trades >= 20): no pairs "
            "qualify."
        )
    else:
        holy_grail.to_csv(RESULTS_DIR / "FnO_Holy_Grail_Pairs.csv", index=False)
        logger.info("Holy Grail pairs:\n%s", holy_grail[REPORT_COLUMNS].to_string(index=False))

    top3 = report.sort_values("IS Sharpe", ascending=False).head(3)
    logger.info(
        "Top 3 pairs by in-sample Sharpe (chosen without looking at OOS):\n%s",
        top3[REPORT_COLUMNS].to_string(index=False),
    )
    return report
