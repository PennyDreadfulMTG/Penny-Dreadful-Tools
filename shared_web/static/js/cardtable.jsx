import { Table, renderRecord, renderWinPercent } from "./table";
import React from "react";
import { render } from "react-dom";

const renderCard = (card) => (
    <React.Fragment>
        <a href={card.url} className="card">{card.name}</a>
        { card.pdLegal
            ? ""
            : <span className="illegal"></span>
        }
    </React.Fragment>
);

const renderHeaderRow = (table) => (
    <tr>
        <th className="name" onClick={table.sort.bind(table, "name", "ASC")}>Card</th>
        <th className="n num-decks" onClick={table.sort.bind(table, "numDecks", "DESC")}># Decks</th>
        <th className="n card-record" onClick={table.sort.bind(table, "record", "DESC")}>Record</th>
        <th className="n win-percent" onClick={table.sort.bind(table, "winPercent", "DESC")}>Win %</th>
        <th className="n tournament-wins" onClick={table.sort.bind(table, "tournamentWins", "DESC")}>
            <abbr title="Tournament wins">①</abbr>
        </th>
        <th className="n tournament-top-8s" onClick={table.sort.bind(table, "tournamentTop8s", "DESC")}>
            <abbr title="Tournament Top 8s">⑧</abbr>
        </th>
        { table.props.tournamentOnly
            ? null
            : <th className="n perfect-runs" onClick={table.sort.bind(table, "perfectRuns", "DESC")}><abbr title="League 5-0 runs">5–0s</abbr></th>
        }
    </tr>
);

const renderRow = (table, card) => (
    <tr key={card.name} className="cardrow" data-cardname={card.name}>
        <td className="name">{renderCard(card)}</td>
        <td className="n">{card.numDecks}</td>
        <td className="n">{renderRecord(card)}</td>
        <td className="n">{renderWinPercent(card)}</td>
        <td className="n">
            { card.tournamentWins > 0
                ? card.tournamentWins
                : ""
            }
        </td>
        <td className="n">
            { card.tournamentTop8s > 0
                ? card.tournamentTop8s
                : ""
            }
        </td>
        { table.props.tournamentOnly
            ? null
            : <td className="n">
                { card.perfectRuns > 0
                    ? card.perfectRuns
                    : ""
                }
            </td>
        }
    </tr>
);


[...document.getElementsByClassName("cardtable")].forEach((e) => {
    if (e !== null) {
        const table =
            <Table
                endpoint="/api/cards2/"
                renderHeaderRow={renderHeaderRow}
                renderRow={renderRow}
                searchPrompt={"Card name"}
                showSearch={true}
                {...e.dataset}
            />;
        render(table, e);
    }
});
