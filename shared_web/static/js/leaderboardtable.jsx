import React from "react";
import Table from "./table";
import { render } from "react-dom";

const renderHeaderRow = (table) => (
    <tr>
        <td className="marginalia"></td>
        <th className="name" onClick={table.sort.bind(table, "name", "ASC")}>Person</th>
        { table.props.skinnyView
            ? null
            : <th className="n num-decks" onClick={table.sort.bind(table, "numDecks", "DESC")}>#</th>
        }
        { table.props.skinnyView
            ? null
            : <th className="n wins" onClick={table.sort.bind(table, "wins", "DESC")}>Wins</th>
        }
        <th className="n points" onClick={table.sort.bind(table, "points", "DESC")}>Pts</th>
    </tr>
);

const renderRow = (table, entry) => (
    <tr key={entry.personId}>
        <td className="marginalia">{entry.position}</td>
        <td className="name"><a href={entry.url}>{entry.person}</a></td>
        { table.props.skinnyView
            ? null
            : <td className="n">{entry.numDecks}</td>
        }
        { table.props.skinnyView
            ? null
            : <td className="n">{entry.wins}</td>
        }
        <td className="n">{entry.points}</td>
    </tr>
);

[...document.getElementsByClassName("leaderboardtable")].forEach((e) => {
    if (e !== null) {
        const table =
            <Table
                className="with-marginalia"
                endpoint="/api/leaderboards/"
                renderHeaderRow={renderHeaderRow}
                renderRow={renderRow}
                showSearch={true}
                type="Person"
                {...e.dataset}
            />;
        render(table, e);
    }
});
