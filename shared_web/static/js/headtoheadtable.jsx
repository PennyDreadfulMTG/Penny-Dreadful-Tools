import { Table, renderRecord, renderWinPercent } from "./table";
import React from "react";
import { render } from "react-dom";

const renderHeaderRow = (table) => (
    <tr>
        <th className="name" onClick={table.sort.bind(table, "name", "ASC")}>Opponent</th>
        <th className="n num-matches" onClick={table.sort.bind(table, "numMatches", "DESC")}># Matches</th>
        <th className="n record" onClick={table.sort.bind(table, "record", "DESC")}>Record</th>
        <th className="n win-percent"onClick={table.sort.bind(table, "winPercent", "DESC")}>Win %</th>
    </tr>
);

const renderRow = (table, entry) => (
    <tr key={entry.oppMtgoUsername}>
        <td className="name"><a href={entry.oppUrl}>{entry.oppMtgoUsername}</a></td>
        <td className="n"><a href={entry.url}>{entry.numMatches}</a></td>
        <td className="n">{renderRecord({...entry,...{"showRecord": true}})}</td>
        <td className="n">{renderWinPercent({...entry,...{"showRecord": true}})}</td>
    </tr>
);

[...document.getElementsByClassName("headtoheadtable")].forEach((e) => {
    if (e !== null) {
        const table =
            <Table
                endpoint="/api/h2h/"
                renderHeaderRow={renderHeaderRow}
                renderRow={renderRow}
                searchPrompt="Opponent name"
                showSearch={true}
                {...e.dataset}
            />;
        render(table, e);
    }
});
