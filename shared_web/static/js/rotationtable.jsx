import { Table, renderCard } from "./table";
import React from "react";
import { createRoot } from "react-dom/client";

const renderHeaderRow = (table) => (
    <tr>
        <th className="hit-in-last-run" onClick={table.sort.bind(table, "hitInLastRun", "DESC")}>⇅</th>
        <th className="name" onClick={table.sort.bind(table, "name", "ASC")}>Card</th>
        <th className="n hits" onClick={table.sort.bind(table, "hits", "DESC")}>Hits</th>
        <th className="n hits-needed" onClick={table.sort.bind(table, "hitsNeeded", "ASC")}>Needed</th>
        <th className="n rank" onClick={table.sort.bind(table, "rank", "ASC")}>Rank</th>
    </tr>
);

const renderRow = (table, card) => (
    <tr key={card.name} data-href={card.url} className={"legality-" + card.status.toLowerCase().replaceAll(" ", "-") + " clickable"}>
        <td>
            { card.hitInLastRun
                ? <span title="Present in last run" className="last-run">↑</span>
                : <span title="Not present in last run" className="last-run">↓</span>
            }
        </td>
        <td className="name">{renderCard(card)}</td>
        <td className="n">{card.hits} ({card.percent}%)</td>
        <td className="n">{card.hitsNeeded} ({card.percentNeeded}%)</td>
        <td className="n">{card.displayRank}</td>
    </tr>
);

[...document.getElementsByClassName("rotationtable")].forEach((e) => {
    if (e !== null) {
        const table =
            <Table
                endpoint="/api/rotation/cards/"
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
