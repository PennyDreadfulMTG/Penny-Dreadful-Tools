import React from "react";
import { Table } from "./table";
import { render } from "react-dom";

const renderHeaderRow = (table) => (
    <tr>
        <th className="name" onClick={table.sort.bind(table, "person", "ASC")}>Person</th>
        <th className="name" onClick={table.sort.bind(table, "deckName", "ASC")}>Deck</th>
        <th className="name" onClick={table.sort.bind(table, "opponent", "ASC")}>Opponent</th>
        <th className="name" onClick={table.sort.bind(table, "opponentDeckName", "ASC")}>Opponent Deck</th>
        <th className="n mtgo-id" onClick={table.sort.bind(table, "mtgoId", "ASC")}>MTGO ID</th>
        <th className="date" onClick={table.sort.bind(table, "date", "DESC")}>Date</th>
        <th>Result</th>
        <th>Delete</th>
    </tr>
);

const renderRow = (table, entry) => (
    <tr key={entry.id}>
        <td className="name"><a href={entry.personUrl}>{entry.person}</a></td>
        <td className="deck-name"><a href={entry.deckUrl}>{entry.deckName}</a></td>
        <td className="name"><a href={entry.opponentUrl}>{entry.opponent}</a></td>
        <td className="deck-name"><a href={entry.opponentDeckUrl}>{entry.opponentDeckName}</a></td>
        <td className="n">
            { entry.mtgoId
                ? <a href={entry.logUrl}>{entry.mtgoId}</a>
                : "Manually Reported"
            }
        </td>
        <td className="date">{entry.displayDate}</td>
        <td>
            <form method="post" className="inline">
                <input type="hidden" name="match_id" defaultValue={entry.id}/>
                <input type="hidden" name="left_id" defaultValue={entry.deckId}/>
                <input type="hidden" name="right_id" defaultValue={entry.opponentDeckId}/>
                <input type="number" name="left_games" defaultValue={entry.gameWins}/>
                <input type="number" name="right_games" defaultValue={entry.gameLosses}/>
                <button name="action" value="change" type="submit">Change</button>
            </form>
        </td>
        <td>
            <form method="post" className="inline">
                <input type="hidden" name="match_id" defaultValue={entry.id}/>
                <button name="action" value="delete" type="submit">Delete</button>
            </form>
        </td>
    </tr>
);

[...document.getElementsByClassName("matchtable")].forEach((e) => {
    if (e !== null) {
        const table =
            <Table
                endpoint="/api/matches/"
                renderHeaderRow={renderHeaderRow}
                renderRow={renderRow}
                showSearch={true}
                searchPrompt="MTGO username"
                {...e.dataset}
            />;
        render(table, e);
    }
});
