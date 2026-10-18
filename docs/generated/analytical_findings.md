# Verified Analytical Findings

_Computed from PostgreSQL on 2026-10-13; each statement below is a direct SQL aggregation of `retailiq.v_sales`. They describe what the data shows, not why._

## Headline figures
- Period covered: 2011-01-01 to 2014-12-31.
- Total sales $12,642,905, total profit $1,467,457, profit margin 11.6%.
- 25,035 orders (51,290 order lines), 4,873 customers, 178,312 units sold.
- Average order value $505; average line discount 14.3%.

## Sales and profit by category
- Technology: sales $4,744,691, profit $663,779, margin 14.0%.
- Furniture: sales $4,110,884, profit $285,205, margin 6.9%.
- Office Supplies: sales $3,787,330, profit $518,474, margin 13.7%.

## Sales by year
- 2011: sales $2,259,511, profit $248,941.
- 2012: sales $2,677,493, profit $307,415 (+18.5% vs previous year).
- 2013: sales $3,405,860, profit $406,935 (+27.2% vs previous year).
- 2014: sales $4,300,041, profit $504,166 (+26.3% vs previous year).

## Markets (by sales)
- APAC: sales $3,585,833, profit $436,000, margin 12.2%.
- EU: sales $2,938,139, profit $372,830, margin 12.7%.
- US: sales $2,297,354, profit $286,397, margin 12.5%.
- LATAM: sales $2,164,687, profit $221,643, margin 10.2%.
- EMEA: sales $806,184, profit $43,898, margin 5.5%.
- Africa: sales $783,776, profit $88,872, margin 11.3%.
- Canada: sales $66,932, profit $17,817, margin 26.6%.

## Regions (by profit)
- Most profitable region: Central (profit $311,404 on sales $2,822,399).
- Least profitable region: Canada (profit $17,817 on sales $66,932).

## Sub-categories (by profit)
- Highest profit: Copiers ($258,568), Phones ($216,717), Bookcases ($161,924).
- Loss-making sub-categories: Tables (-$64,083).

## Customer segments
- Consumer: sales $6,508,141, profit $749,240.
- Corporate: sales $3,824,808, profit $441,208.
- Home Office: sales $2,309,956, profit $277,009.

## Discounts and profitability
Profit margin by line-discount band (profit / sales within the band):
- none: margin 25.3% over 29,009 order lines.
- up to 10%: margin 17.2% over 4,679 order lines.
- 10-20%: margin 9.9% over 6,274 order lines.
- 20-30%: margin -5.5% over 967 order lines.
- 30-50%: margin -32.4% over 6,189 order lines.
- over 50%: margin -111.0% over 4,172 order lines.

## Shipping
- Same Day: 1,347 orders, average 0.0 days to ship, average shipping cost 42.94.
- First Class: 3,821 orders, average 2.2 days to ship, average shipping cost 41.05.
- Second Class: 5,119 orders, average 3.2 days to ship, average shipping cost 30.47.
- Standard Class: 15,154 orders, average 5.0 days to ship, average shipping cost 19.97.

## Best-selling products
- Apple Smart Phone, Full Size ($86,936); Cisco Smart Phone, Full Size ($76,441); Motorola Smart Phone, Full Size ($73,159).
