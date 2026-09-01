import { Table, renderCard } from "./table";
import Axios from "axios";
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

class RotationTable extends Table {
    downloadCSV() {
        const { q, sortBy, sortOrder } = this.state;
        const params = { q, sortBy, sortOrder, pageSize: 99999, page: 0 };
        Axios.get("/api/rotation/cards/", { params }).then((response) => {
            const headers = ["name", "hits", "hitsNeeded", "percent", "percentNeeded", "rank"];
            const rows = response.data.objects.map((card) =>
                headers.map((h) => JSON.stringify(card[h] ?? "")).join(",")
            );
            const csv = [headers.join(","), ...rows].join("\n");
            const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
            const a = document.createElement("a");
            a.href = url;
            a.download = "rotation.csv";
            a.click();
            URL.revokeObjectURL(url);
        });
    }

    render() {
        const result = super.render();
        if (!this.state.loadedOnce) {
            return result;
        }
        return (
            <React.Fragment>
                {result}
                <button className="download-csv" onClick={this.downloadCSV.bind(this)}>Download CSV</button>
            </React.Fragment>
        );
    }
}

[...document.getElementsByClassName("rotationtable")].forEach((e) => {
    if (e !== null) {
        const table =
            <RotationTable
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
