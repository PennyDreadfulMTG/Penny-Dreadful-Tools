import { Table, renderCard } from "./table";
import React from "react";
import { render } from "react-dom";

const renderHeaderRow = (table) => (
    <tr>
        <th className="hit-in-last-run" onClick={table.sort.bind(table, "hitInLastRun", "DESC")}>⇅</th>
        <th className="name" onClick={table.sort.bind(table, "name", "ASC")}>Card</th>
        <th className="n hits" onClick={table.sort.bind(table, "hits", "DESC")}>Hits</th>
        <th className="n hits-needed" onClick={table.sort.bind(table, "hitsNeeded", "ASC")}>Needed</th>
    </tr>
);

const renderRow = (table, card) => (
    <tr key={card.name} className={"legality-" + card.status.toLowerCase().replaceAll(" ", "-")}>
        <td>
            { card.hitInLastRun
                ? "↑"
                : "↓"
            }
        </td>
        <td className="name">{renderCard(card)}</td>
        <td className="n">{card.hits} ({card.percent}%)</td>
        <td className="n">{card.hitsNeeded} ({card.percentNeeded}%)</td>
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
        render(table, e);
    }
});
