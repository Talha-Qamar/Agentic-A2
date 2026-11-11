FROM python:3.12-slim
WORKDIR /app
COPY . /src/gigbid_portfolio_pkg
RUN pip install --no-cache-dir "/src/gigbid_portfolio_pkg[dense]"
ENV PORTFOLIO_DIR=/portfolio
VOLUME ["/portfolio"]
ENTRYPOINT ["gigbid-portfolio-mcp"]
