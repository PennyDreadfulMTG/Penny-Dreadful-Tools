import { Table, renderRecord, renderWinPercent } from "./table";
import React from "react";
import { render } from "react-dom";

const renderHeaderRow = (table) => (
    <tr>
        <th className="name">Name</th>
        <th className="n num-decks" onClick={table.sort.bind(table, "numDecks", "DESC")}>Decks</th>
        <th className="n record" onClick={table.sort.bind(table, "record", "DESC")}>Record</th>
        <th className="n win-percent" onClick={table.sort.bind(table, "winPercent", "DESC")}>Win %</th>
        <th className="n tournament-wins" onClick={table.sort.bind(table, "tournamentWins", "DESC")}>
            <abbr title="Tournament wins">①</abbr>
        </th>
        <th className="n tournament-top-8s" onClick={table.sort.bind(table, "tournamentTop8s", "DESC")}>
            <abbr title="Tournament top-8s">⑧</abbr>
        </th>
        <th className="n perfect-runs divider" onClick={table.sort.bind(table, "perfectRuns", "DESC")}>
            <abbr title="League 5-0 runs">5–0s</abbr>
        </th>
        <th className="n elo" onClick={table.sort.bind(table, "elo", "DESC")}>Elo</th>
    </tr>
);

const renderRow = (table, person) => (
    <tr key={person.id}>
        <td className="name"><a href={person.url}>{person.name}</a></td>
        <td className="n"><a href={person.url}>{person.numDecks}</a></td>
        <td className="n">{renderRecord(person)}</td>
        <td className="n">{renderWinPercent(person)}</td>
        <td className="n">
            { person.tournamentTop8s
                ? person.tournamentWins
                : ""
            }
        </td>
        <td className="n">
            { person.tournamentTop8s
                ? person.tournamentTop8s
                : ""
            }
        </td>
        <td className="n divider">
            { person.perfectRuns
                ? person.perfectRuns
                : ""
            }
        </td>
        <td className="n">
            { person.showRecord
                ? <a href={person.url}>{person.elo}</a>
                : ""
            }
        </td>
    </tr>
);

[...document.getElementsByClassName("persontable")].forEach((e) => {
    if (e !== null) {
        const table =
            <Table
                endpoint="/api/people/"
                renderHeaderRow={renderHeaderRow}
                renderRow={renderRow}
                showSearch={true}
                type="Person"
                {...e.dataset}
            />;
        render(table, e);
    }
});
