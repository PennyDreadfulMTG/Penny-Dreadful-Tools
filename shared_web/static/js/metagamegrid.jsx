import { Grid } from "./grid";
import React from "react";
import { createRoot } from "react-dom/client";

const n = (num) => {
    if (num < 1) {
        return Number(num).toPrecision(1).toLocaleString();
    }
    return Number(Math.round(num)).toLocaleString();
};

//  once everything is in place mouseover everything and makes ure the titles are right
const renderItem = (grid, archetype) => (
    <a className="archetype" href={archetype.url} key={archetype.id}>
        <div className="row archetype-name">
            {archetype.name}
        </div>
        <div className="row key-card">
            {archetype.keyCards.length > 0 && (
                <div className="card" data-name={archetype.keyCards[0].name} style={{background: `url(${archetype.keyCards[0].url}) center top / cover no-repeat`}}></div>
            )}
        </div>
        <div className="row flex-row">
            <div title="Meta Share" className="stacked-bar stacked-bar-highlight" style={{width: `${archetype.metaShare * 100}%`}}></div>
            <div className="percentage-with-additional" style={{marginLeft: "8px", width: `${100 - archetype.metaShare}%`}}>
                <span title="Meta Share" className="percentage">
                    {n(archetype.metaShare * 100)}%
                </span>
                <span className="additional">
                    <span title="Number of Decks">
                        #{n(archetype.numDecks)}
                    </span>
                    <span title="Number of Matches">
                        ⚔{n(archetype.numMatches)}
                    </span>
                </span>
            </div>
        </div>
        <div className="row">
            <div className="colors" title="Deck Colors" dangerouslySetInnerHTML={{__html: archetype.colorsSafe}}></div>
        </div>
        <div className="row">
            <div className="percentage-with-additional">
                <span className={"percentage"} title="Win %">
                    {n(archetype.winPercent)}%
                </span>
                {" "}
                <span className={"additional"} title="Win-Loss Record">
                    {n(archetype.wins)}–{n(archetype.losses)}
                </span>
            </div>
        </div>
        <div className="row flex-row">
            <div className="cell">
                <span title="Tournament Wins">
                    ① {n(archetype.tournamentWins)}
                </span>
            </div>
            <div className="cell c">
                <span title="Tournament Top 8s">
                    ⑧ {n(archetype.tournamentTop8s)}
                </span>
            </div>
            {!grid.props.tournamentOnly && (
                <div className="cell r">
                    <span title="5–0 League Runs">
                        ⁙ {n(archetype.perfectRuns)}
                    </span>
                </div>
            )}
        </div>
        <div className="row key-cards">
            {archetype.keyCards && archetype.keyCards.shift() && archetype.keyCards.map((card) => (
                <div className="card" data-name={card.name} style={{background: `url(${card.url}) center top / cover no-repeat`}} key={card.name}></div>
            ))}
        </div>
    </a>
);

const renderSort = (grid) => (
    <React.Fragment>
        {"Sorted by "}
        <form className="inline">
            <select onChange={(e) => { grid.sort(e.target.value, grid.state.sortOrder); }}>
                <option value="quality">Quality</option>
                <option value="metaShare">Meta Share</option>
                <option value="winPercent">Win %</option>
                <option value="tournamentWins">Tournament Wins</option>
                <option value="tournamentTop8s">Tournament Top 8s</option>
                <option value="perfectRuns">League 5–0 Runs</option>
                <option value="name">Name</option>
            </select>
            {" : "}
            <select onChange={(e) => { grid.sort(grid.state.sortBy, e.target.value); }}>
                <option value="AUTO">Auto</option>
                <option value="ASC">Asc</option>
                <option value="DESC">Desc</option>
            </select>
        </form>
    </React.Fragment>
);

[...document.getElementsByClassName("metagamegrid")].forEach((e) => {
    if (e !== null) {
        const grid =
            <Grid
                className="metagame-grid"
                endpoint="/api/archetypes2/"
                renderItem={renderItem}
                renderSort={renderSort}
                reloadCards={true}
                searchPrompt={"Archetype name"}
                showSearch={true}
                {...e.dataset}
            />;
        createRoot(e).render(grid);
    }
});
