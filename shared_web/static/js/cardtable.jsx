import { Table, renderCard, renderRecord, renderWinPercent } from "./table";
import React from "react";
import { createRoot } from "react-dom/client";

const renderHeaderRow = (table) => (
    <tr>
        <th className="name" onClick={table.sort.bind(table, "name", "ASC")}>Card</th>
        <th className="n num-decks" onClick={table.sort.bind(table, "numDecks", "DESC")}># Decks</th>
        <th className="n card-record" onClick={table.sort.bind(table, "record", "DESC")}>Record</th>
        <th className="n win-percent" onClick={table.sort.bind(table, "winPercent", "DESC")}>Win %</th>
        { table.props.leagueOnly
            ? null
            : <th className="n tournament-wins" onClick={table.sort.bind(table, "tournamentWins", "DESC")}>
                <abbr title="Tournament wins">①</abbr>
            </th>
        }
        { table.props.leagueOnly
            ? null
            : <th className="n tournament-top-8s" onClick={table.sort.bind(table, "tournamentTop8s", "DESC")}>
                <abbr title="Tournament Top 8s">⑧</abbr>
            </th>
        }
        { table.props.tournamentOnly
            ? null
            : <th className="n perfect-runs" onClick={table.sort.bind(table, "perfectRuns", "DESC")}><abbr title="League 5-0 runs">5–0s</abbr></th>
        }
    </tr>
);

const renderRow = (table, card) => (
    <tr key={card.name}  onClick={() => window.location.href = card.url} className="clickable">
        <td className="name">{renderCard(card)}</td>
        <td className="n">{card.numDecks}</td>
        <td className="n">{renderRecord(card)}</td>
        <td className="n">{renderWinPercent(card)}</td>
        { table.props.leagueOnly
            ? null
            : <td className="n">
                { card.tournamentWins > 0
                    ? card.tournamentWins
                    : ""
                }
            </td>
        }
        { table.props.leagueOnly
            ? null
            : <td className="n">
                { card.tournamentTop8s > 0
                    ? card.tournamentTop8s
                    : ""
                }
            </td>
        }
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
                searchPrompt={"Scryfall search"}
                showSearch={true}
                reloadCards={true}
                {...e.dataset}

            />;
        createRoot(e).render(table);
    }
});
