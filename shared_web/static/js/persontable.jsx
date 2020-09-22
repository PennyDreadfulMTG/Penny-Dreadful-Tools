import { Table, renderRecord, renderWinPercent } from "./table";
import React from "react";
import { render } from "react-dom";

const renderHeaderRow = (table) => (
    <tr>
        <th>Name</th>
        <th className="n" onClick={table.sort.bind(table, "", "DESC")}>Decks</th>
        <th className="n" onClick={table.sort.bind(table, "", "DESC")}>Record</th>
        <th className="n" onClick={table.sort.bind(table, "", "DESC")}>Win %</th>
        <th className="n" onClick={table.sort.bind(table, "", "DESC")}>
            <abbr title="Tournament wins">①</abbr>
        </th>
        <th className="n" onClick={table.sort.bind(table, "", "DESC")}>
            <abbr title="Tournament top-8s">⑧</abbr>
        </th>
        <th className="n divider" onClick={table.sort.bind(table, "", "DESC")}>
            <abbr title="League 5-0 runs">5–0s</abbr>
        </th>
        <th className="n" onClick={table.sort.bind(table, "", "DESC")}>Elo</th>
    </tr>
);

const renderRow = (table, person) => (
    if (!person.numDecks) {
        return null; // BAKERT does this work to elide a row or does the logic have to live higher up/should it?
    }
    <tr key={person.id}>
        <td><a href={person.url}>{person.name}</a></td>
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
                endpoint="/api/cards2/"
                renderHeaderRow={renderHeaderRow}
                renderRow={renderRow}
                showSearch={true}
                type="Card"
                {...e.dataset}
            />;
        render(table, e);
    }
});
