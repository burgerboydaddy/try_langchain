from langchain_core.tools import tool
import yfinance as yf

@tool
def get_stock_data(ticker: str) -> str:
    """Get the current stock data for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if data.empty:
            return f"Error: No data found for ticker {ticker}."
        
        latest = data.iloc[-1]
        return (
            f"Current stock data for {ticker}:\n"
            f"- Open: {latest['Open']:.2f}\n"
            f"- High: {latest['High']:.2f}\n"
            f"- Low: {latest['Low']:.2f}\n"
            f"- Close: {latest['Close']:.2f}\n"
            f"- Volume: {latest['Volume']}"
        )
    except Exception as exc:
        return f"Error: {exc}"
