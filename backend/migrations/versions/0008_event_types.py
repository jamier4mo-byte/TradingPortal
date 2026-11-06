"""Seed the event types with plain-English explanations (News Room 3.3).

Each row: key, currency, canonical name, category, higher_is_better, explanation, why_it_matters, aliases.

`higher_is_better` is from the currency's point of view: True when a higher actual than forecast tends to
strengthen the currency (stronger growth, hotter inflation → a more hawkish central bank → currency up);
False when lower is better (unemployment rate, jobless claims); None when there's no better/worse reading
(speeches, statements, press conferences, minutes).

Aliases cover Forex Factory titles and the JBlanked / MQL5 names. An alias with "*" is a wildcard pattern
(used for speeches, e.g. "Fed Chair * Speaks"). Matching is per currency, case- and punctuation-insensitive.
Unknown feed titles create unseeded event types at run time (no explanation yet).

Revision ID: 0008
Revises: 0007
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# (key, currency, name, category, higher_is_better, explanation, why_it_matters, aliases)
# fmt: off
SEED_EVENT_TYPES: list[tuple[str, str, str, str, bool | None, str, str, list[str]]] = [
    # ---- USD -------------------------------------------------------------------------------------
    (
        "USD:nfp", "USD", "Non-Farm Payrolls", "employment", True,
        "The number of jobs added or lost in the US outside farming over the last month, from the "
        "Bureau of Labor Statistics. Released on the first Friday of most months at 08:30 New York time.",
        "The biggest scheduled US release. A big beat or miss moves the dollar, gold and US indices "
        "sharply in the first minutes, and it shapes expectations for the Fed's next move.",
        ["Non-Farm Employment Change", "Nonfarm Payrolls", "Non-Farm Payrolls", "Nonfarm Employment Change"],
    ),
    (
        "USD:adp", "USD", "ADP Non-Farm Employment Change", "employment", True,
        "Private-sector job growth estimated by the payroll firm ADP, released two days before the "
        "official jobs report.",
        "Read as an early hint for Non-Farm Payrolls, though the two often disagree. A large surprise "
        "can move the dollar and gold on its own.",
        ["ADP Non-Farm Employment Change", "ADP Nonfarm Employment Change", "ADP Employment Change"],
    ),
    (
        "USD:unemployment_rate", "USD", "Unemployment Rate", "employment", False,
        "The share of the US labour force that is out of work and looking for a job, released with "
        "Non-Farm Payrolls.",
        "A rising rate points to a cooling economy and earlier Fed rate cuts, which tends to weaken the "
        "dollar. Traders read it alongside payrolls and wages.",
        ["Unemployment Rate"],
    ),
    (
        "USD:claims", "USD", "Unemployment Claims", "employment", False,
        "The number of people filing for unemployment benefit for the first time in the past week. "
        "Released every Thursday at 08:30 New York time.",
        "The most timely read on US layoffs. A run of high claims signals a weakening jobs market; a "
        "single big surprise can nudge the dollar and gold.",
        ["Unemployment Claims", "Initial Jobless Claims", "Jobless Claims"],
    ),
    (
        "USD:ahe", "USD", "Average Hourly Earnings m/m", "employment", True,
        "The monthly change in what US workers earn per hour, released with Non-Farm Payrolls.",
        "Wage growth feeds inflation, so hot earnings make the Fed more hawkish and can lift the dollar "
        "even when the headline jobs number disappoints.",
        ["Average Hourly Earnings m/m", "Average Hourly Earnings"],
    ),
    (
        "USD:cpi_mm", "USD", "CPI m/m", "inflation", True,
        "The monthly change in the prices US consumers pay for a basket of goods and services, from the "
        "Bureau of Labor Statistics.",
        "Inflation drives Fed policy. A hotter print makes rate cuts less likely and tends to lift the "
        "dollar and weigh on gold and US indices.",
        ["CPI m/m", "Consumer Price Index m/m"],
    ),
    (
        "USD:core_cpi_mm", "USD", "Core CPI m/m", "inflation", True,
        "The monthly change in US consumer prices excluding food and energy, which swing a lot.",
        "The Fed and the market watch core inflation most closely, so this is usually the CPI number "
        "that moves the dollar, gold and the Nasdaq.",
        ["Core CPI m/m", "Core Consumer Price Index m/m"],
    ),
    (
        "USD:cpi_yy", "USD", "CPI y/y", "inflation", True,
        "How much US consumer prices have risen over the past twelve months.",
        "The headline inflation rate the Fed's 2% target is judged against. Released alongside the "
        "monthly CPI figures, so the market reacts to all of them together.",
        ["CPI y/y", "Consumer Price Index y/y"],
    ),
    (
        "USD:ppi_mm", "USD", "PPI m/m", "inflation", True,
        "The monthly change in prices that US producers receive for their goods and services.",
        "Producer prices can pass through to consumers, so a hot PPI hints at future inflation. Usually "
        "a smaller mover than CPI unless the surprise is large.",
        ["PPI m/m", "Producer Price Index m/m", "Core PPI m/m"],
    ),
    (
        "USD:core_pce_mm", "USD", "Core PCE Price Index m/m", "inflation", True,
        "The monthly change in US consumer prices excluding food and energy, measured from personal "
        "spending data. It is the Fed's preferred inflation gauge.",
        "Because the Fed targets PCE inflation, a surprise here can shift rate expectations, though CPI "
        "earlier in the month often takes the edge off the reaction.",
        ["Core PCE Price Index m/m", "Core PCE Price Index", "Core PCE Prices m/m"],
    ),
    (
        "USD:fed_rate", "USD", "Federal Funds Rate", "central_bank", True,
        "The Federal Reserve's interest-rate decision, announced at 14:00 New York time after each of "
        "its eight yearly meetings.",
        "The rate itself is usually expected; the surprise is in the statement and the vote. A hawkish "
        "turn lifts the dollar and can hit gold and the Nasdaq hard.",
        ["Federal Funds Rate", "Fed Interest Rate Decision", "Fed Funds Rate"],
    ),
    (
        "USD:fomc_statement", "USD", "FOMC Statement", "central_bank", None,
        "The written statement the Fed releases with its rate decision, explaining its view of the "
        "economy and where policy is heading.",
        "Small changes in wording can move markets as much as the decision itself. Expect fast, "
        "two-way moves in the dollar, gold and US indices.",
        ["FOMC Statement"],
    ),
    (
        "USD:fomc_press_conference", "USD", "FOMC Press Conference", "central_bank", None,
        "The Fed Chair's press conference 30 minutes after the rate decision, with questions from "
        "journalists.",
        "Answers can confirm or undo the market's first read of the statement, so the second move "
        "often starts here.",
        ["FOMC Press Conference"],
    ),
    (
        "USD:fomc_minutes", "USD", "FOMC Meeting Minutes", "central_bank", None,
        "The detailed record of the Fed's previous meeting, published three weeks later.",
        "Shows how many members leaned hawkish or dovish. Usually a smaller mover, but a surprise in "
        "tone can shift rate expectations.",
        ["FOMC Meeting Minutes", "FOMC Minutes"],
    ),
    (
        "USD:fed_chair_speaks", "USD", "Fed Chair Speaks", "speech", None,
        "A public speech or testimony by the Chair of the Federal Reserve.",
        "Any hint about the path of rates can move the dollar, gold and indices, especially when the "
        "speech comes with questions from the audience.",
        ["Fed Chair * Speaks", "Fed Chair * Speech", "Fed Chair * Testifies", "Fed Chairman * Speaks"],
    ),
    (
        "USD:advance_gdp", "USD", "Advance GDP q/q", "growth", True,
        "The first estimate of how fast the US economy grew last quarter, shown as an annualised rate.",
        "The broadest growth measure. A big miss raises recession worries and rate-cut bets; a beat "
        "supports the dollar.",
        ["Advance GDP q/q", "GDP q/q", "GDP Growth Rate q/q"],
    ),
    (
        "USD:ism_manufacturing", "USD", "ISM Manufacturing PMI", "business", True,
        "A monthly survey of US factory purchasing managers. Above 50 means activity is expanding; below "
        "50 means it is shrinking.",
        "An early read on US growth. The prices-paid and employment parts can matter as much as the "
        "headline.",
        ["ISM Manufacturing PMI"],
    ),
    (
        "USD:ism_services", "USD", "ISM Services PMI", "business", True,
        "A monthly survey of US service-sector purchasing managers. Above 50 means expansion.",
        "Services are most of the US economy, so this survey can move the dollar more than its "
        "manufacturing twin.",
        ["ISM Services PMI", "ISM Non-Manufacturing PMI"],
    ),
    (
        "USD:retail_sales", "USD", "Retail Sales m/m", "consumer", True,
        "The monthly change in the value of sales at US retailers.",
        "Consumer spending drives the US economy. A strong number supports the dollar and growth "
        "expectations.",
        ["Retail Sales m/m", "Retail Sales"],
    ),
    (
        "USD:core_retail_sales", "USD", "Core Retail Sales m/m", "consumer", True,
        "Retail sales excluding cars, which swing a lot from month to month.",
        "Gives a cleaner read of underlying spending, so traders often weigh it above the headline.",
        ["Core Retail Sales m/m", "Retail Sales Ex Autos m/m", "Retail Sales ex Autos m/m"],
    ),
    (
        "USD:jolts", "USD", "JOLTS Job Openings", "employment", True,
        "The number of unfilled job vacancies in the US at the end of the month before last.",
        "Shows how tight the jobs market is. Falling openings point to cooling wage pressure and a "
        "softer Fed.",
        ["JOLTS Job Openings"],
    ),
    (
        "USD:uom_sentiment", "USD", "UoM Consumer Sentiment", "consumer", True,
        "The University of Michigan survey of how US consumers feel about their finances and the "
        "economy, published as a preliminary and a revised reading each month.",
        "Moves markets mainly through its inflation-expectations questions, which the Fed watches.",
        [
            "Prelim UoM Consumer Sentiment",
            "Revised UoM Consumer Sentiment",
            "UoM Consumer Sentiment",
            "Michigan Consumer Sentiment",
            "Michigan Consumer Sentiment Prelim",
        ],
    ),
    (
        "USD:cb_confidence", "USD", "CB Consumer Confidence", "consumer", True,
        "The Conference Board's monthly survey of US consumer confidence in the economy and jobs.",
        "A guide to future spending. Usually a modest mover unless it surprises a lot.",
        ["CB Consumer Confidence", "CB Consumer Confidence Index"],
    ),
    # ---- EUR -------------------------------------------------------------------------------------
    (
        "EUR:ecb_rate", "EUR", "Main Refinancing Rate", "central_bank", True,
        "The European Central Bank's main interest rate, announced after each policy meeting.",
        "The decision is usually expected; the statement and the press conference that follows drive "
        "the euro and the DAX.",
        [
            "Main Refinancing Rate",
            "ECB Interest Rate Decision",
            "Deposit Facility Rate",
            "ECB Deposit Facility Rate",
            "Monetary Policy Statement",
        ],
    ),
    (
        "EUR:ecb_press_conference", "EUR", "ECB Press Conference", "central_bank", None,
        "The ECB President's press conference 45 minutes after the rate decision.",
        "Guidance on future rate moves comes here, so the euro often makes its main move during the "
        "questions.",
        ["ECB Press Conference"],
    ),
    (
        "EUR:ecb_president_speaks", "EUR", "ECB President Speaks", "speech", None,
        "A public speech or testimony by the President of the European Central Bank.",
        "Hints about rates or inflation can move the euro and European indices.",
        ["ECB President * Speaks", "ECB President * Speech", "ECB President * Testifies"],
    ),
    (
        "EUR:cpi_flash", "EUR", "CPI Flash Estimate y/y", "inflation", True,
        "The first estimate of euro-area inflation over the past twelve months, published at the end "
        "of the month.",
        "The ECB's target is 2%, so a hot flash print makes rate cuts less likely and supports the euro.",
        ["CPI Flash Estimate y/y", "Core CPI Flash Estimate y/y", "Inflation Rate y/y Flash"],
    ),
    (
        "EUR:german_zew", "EUR", "German ZEW Economic Sentiment", "business", True,
        "A monthly survey of financial analysts' expectations for the German economy over the next six "
        "months.",
        "An early read on Europe's largest economy. A big surprise can move the euro and the DAX.",
        ["German ZEW Economic Sentiment", "ZEW Economic Sentiment Indicator"],
    ),
    (
        "EUR:german_ifo", "EUR", "German Ifo Business Climate", "business", True,
        "A monthly survey of around 9,000 German firms on current conditions and their expectations.",
        "One of the best guides to German growth; it matters most for the DAX and the euro.",
        ["German Ifo Business Climate", "Ifo Business Climate"],
    ),
    (
        "EUR:flash_manufacturing_pmi", "EUR", "Flash Manufacturing PMI", "business", True,
        "The first estimate of the euro-area factory purchasing managers' survey. Above 50 means "
        "expansion.",
        "Arrives before the official data, so it is an early guide to euro-area growth.",
        ["Flash Manufacturing PMI", "HCOB Manufacturing PMI", "HCOB Eurozone Manufacturing PMI"],
    ),
    (
        "EUR:flash_services_pmi", "EUR", "Flash Services PMI", "business", True,
        "The first estimate of the euro-area services purchasing managers' survey. Above 50 means "
        "expansion.",
        "Services are most of the euro-area economy; a surprise can move the euro and the DAX.",
        ["Flash Services PMI", "HCOB Services PMI", "HCOB Eurozone Services PMI"],
    ),
    (
        "EUR:german_flash_manufacturing_pmi", "EUR", "German Flash Manufacturing PMI", "business", True,
        "The first estimate of Germany's factory purchasing managers' survey. Above 50 means expansion.",
        "German industry drives the DAX, so this release often moves it more than the euro.",
        ["German Flash Manufacturing PMI", "HCOB Germany Manufacturing PMI"],
    ),
    (
        "EUR:german_flash_services_pmi", "EUR", "German Flash Services PMI", "business", True,
        "The first estimate of Germany's services purchasing managers' survey. Above 50 means expansion.",
        "An early guide to German growth beyond industry; read with the manufacturing survey.",
        ["German Flash Services PMI", "HCOB Germany Services PMI"],
    ),
    (
        "EUR:german_prelim_cpi", "EUR", "German Prelim CPI m/m", "inflation", True,
        "The first estimate of the monthly change in German consumer prices, released before the "
        "euro-area figure.",
        "Germany is the euro area's largest economy, so its inflation print shapes expectations for the "
        "euro-area flash CPI and the ECB.",
        ["German Prelim CPI m/m", "German CPI m/m", "CPI m/m Prelim"],
    ),
    # ---- GBP -------------------------------------------------------------------------------------
    (
        "GBP:boe_rate", "GBP", "Official Bank Rate", "central_bank", True,
        "The Bank of England's interest-rate decision, with the vote split of its nine-member committee.",
        "The vote split is often the surprise. A more hawkish vote than expected lifts the pound.",
        [
            "Official Bank Rate",
            "BoE Interest Rate Decision",
            "MPC Official Bank Rate Votes",
            "Monetary Policy Summary",
        ],
    ),
    (
        "GBP:boe_gov_speaks", "GBP", "BoE Governor Speaks", "speech", None,
        "A public speech or testimony by the Governor of the Bank of England.",
        "Hints about the timing of rate changes can move the pound.",
        ["BOE Gov * Speaks", "BoE Governor * Speaks", "BoE Gov * Speech"],
    ),
    (
        "GBP:cpi_yy", "GBP", "CPI y/y", "inflation", True,
        "How much UK consumer prices have risen over the past twelve months, from the Office for "
        "National Statistics.",
        "The Bank of England targets 2%. A hot print makes rate cuts less likely and lifts the pound.",
        ["CPI y/y", "Consumer Price Index y/y"],
    ),
    (
        "GBP:gdp_mm", "GBP", "GDP m/m", "growth", True,
        "The monthly change in the size of the UK economy.",
        "A clear read on UK growth; a big miss feeds rate-cut bets and weighs on the pound.",
        ["GDP m/m", "GDP Growth Rate m/m"],
    ),
    (
        "GBP:claimant_count", "GBP", "Claimant Count Change", "employment", False,
        "The monthly change in the number of people claiming unemployment-related benefits in the UK.",
        "A rise points to a weakening jobs market. Released with UK wage and unemployment data.",
        ["Claimant Count Change"],
    ),
    (
        "GBP:unemployment_rate", "GBP", "Unemployment Rate", "employment", False,
        "The share of the UK labour force that is out of work, measured over three months.",
        "Read with wage growth: a looser jobs market eases pressure on the Bank of England.",
        ["Unemployment Rate", "ILO Unemployment Rate"],
    ),
    (
        "GBP:retail_sales", "GBP", "Retail Sales m/m", "consumer", True,
        "The monthly change in the volume of sales at UK retailers.",
        "A guide to UK consumer spending; surprises move the pound.",
        ["Retail Sales m/m", "Retail Sales"],
    ),
    (
        "GBP:flash_manufacturing_pmi", "GBP", "Flash Manufacturing PMI", "business", True,
        "The first estimate of the UK factory purchasing managers' survey. Above 50 means expansion.",
        "An early guide to UK growth, published before the official data.",
        ["Flash Manufacturing PMI", "S&P Global Manufacturing PMI", "S&P Global UK Manufacturing PMI"],
    ),
    (
        "GBP:flash_services_pmi", "GBP", "Flash Services PMI", "business", True,
        "The first estimate of the UK services purchasing managers' survey. Above 50 means expansion.",
        "Services dominate the UK economy, so this survey tends to move the pound more than its "
        "manufacturing twin.",
        ["Flash Services PMI", "S&P Global Services PMI", "S&P Global UK Services PMI"],
    ),
    # ---- JPY, AUD, CAD, CHF, NZD -------------------------------------------------------------------
    (
        "JPY:boj_rate", "JPY", "BoJ Policy Rate", "central_bank", True,
        "The Bank of Japan's interest-rate decision. There is no fixed release time; it usually comes "
        "during the Asian morning.",
        "Japan has kept rates very low for years, so any hint of a hike can move the yen sharply.",
        ["BOJ Policy Rate", "BoJ Interest Rate Decision", "Monetary Policy Statement"],
    ),
    (
        "AUD:rba_rate", "AUD", "RBA Cash Rate", "central_bank", True,
        "The Reserve Bank of Australia's interest-rate decision.",
        "The statement's guidance on future moves drives the Australian dollar.",
        ["Cash Rate", "RBA Interest Rate Decision", "RBA Rate Statement"],
    ),
    (
        "AUD:employment_change", "AUD", "Employment Change", "employment", True,
        "The monthly change in the number of employed people in Australia.",
        "A key input for the RBA; big surprises move the Australian dollar.",
        ["Employment Change"],
    ),
    (
        "AUD:unemployment_rate", "AUD", "Unemployment Rate", "employment", False,
        "The share of Australia's labour force that is out of work, released with Employment Change.",
        "Read with the jobs number: a rising rate makes RBA rate cuts more likely.",
        ["Unemployment Rate"],
    ),
    (
        "CAD:boc_rate", "CAD", "BoC Overnight Rate", "central_bank", True,
        "The Bank of Canada's interest-rate decision.",
        "Rate decisions and the statement's guidance move the Canadian dollar.",
        ["Overnight Rate", "BoC Interest Rate Decision", "BOC Rate Statement"],
    ),
    (
        "CAD:employment_change", "CAD", "Employment Change", "employment", True,
        "The monthly change in the number of employed people in Canada. Often released at the same "
        "time as US Non-Farm Payrolls.",
        "Moves the Canadian dollar; when it lands with US payrolls, USDCAD can swing both ways.",
        ["Employment Change"],
    ),
    (
        "CAD:unemployment_rate", "CAD", "Unemployment Rate", "employment", False,
        "The share of Canada's labour force that is out of work, released with Employment Change.",
        "A rising rate points to Bank of Canada rate cuts.",
        ["Unemployment Rate"],
    ),
    (
        "CHF:snb_rate", "CHF", "SNB Policy Rate", "central_bank", True,
        "The Swiss National Bank's interest-rate decision, made once a quarter.",
        "The SNB surprises markets more often than most central banks, so the franc can jump.",
        ["SNB Policy Rate", "SNB Interest Rate Decision", "SNB Monetary Policy Assessment"],
    ),
    (
        "NZD:rbnz_rate", "NZD", "RBNZ Official Cash Rate", "central_bank", True,
        "The Reserve Bank of New Zealand's interest-rate decision.",
        "The decision and the bank's forecast for its own rate path move the New Zealand dollar.",
        ["Official Cash Rate", "RBNZ Interest Rate Decision", "RBNZ Rate Statement"],
    ),
]
# fmt: on


def upgrade() -> None:
    now = datetime.now(UTC)
    table = sa.table(
        "event_types",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("currency", sa.String),
        sa.column("category", sa.String),
        sa.column("higher_is_better", sa.Boolean),
        sa.column("explanation", sa.Text),
        sa.column("why_it_matters", sa.Text),
        sa.column("aliases", sa.JSON),
        sa.column("seeded", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        table,
        [
            {
                "key": key,
                "name": name,
                "currency": cur,
                "category": cat,
                "higher_is_better": hib,
                "explanation": expl,
                "why_it_matters": why,
                "aliases": aliases,
                "seeded": True,
                "created_at": now,
                "updated_at": now,
            }
            for key, cur, name, cat, hib, expl, why, aliases in SEED_EVENT_TYPES
        ],
    )


def downgrade() -> None:
    keys = [row[0] for row in SEED_EVENT_TYPES]
    table = sa.table("event_types", sa.column("key", sa.String))
    op.execute(table.delete().where(table.c.key.in_(keys)))
