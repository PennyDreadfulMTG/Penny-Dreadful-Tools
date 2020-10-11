import { Table, renderRecord } from "./table";
import React from "react";
import { render } from "react-dom";

const renderHeaderRow = (table) => (
    <tr>
        <th className="marginalia" onClick={table.sort.bind(table, "marginalia", "ASC")}>⇅</th>
        <th onClick={table.sort.bind(table, "colors", "ASC")}>Colors</th>
        <th className="deck-name" onClick={table.sort.bind(table, "name", "ASC")}>Name</th>
        { table.props.hidePerson
            ? null
            : <th className="person" onClick={table.sort.bind(table, "person", "ASC")}>Person</th>
        }
        { table.props.showArchetype
            ? <th className="archetype" onClick={table.sort.bind(table, "archetype", "ASC")}>Archetype</th>
            : null
        }
        { table.props.hideSource
            ? null
            : <th className="source" onClick={table.sort.bind(table, "sourceName", "ASC")}>Source</th>
        }
        <th className="n record" onClick={table.sort.bind(table, "record", "DESC")}>Record</th>
        { table.props.showOmw
            ? <th className="omw" title="Opponent's Match Win" onClick={table.sort.bind(table, "omw", "DESC")}>OMW</th>
            : null
        }
        { table.props.hideTop8
            ? null
            : <th className="c top8" onClick={table.sort.bind(table, "top8", "ASC")}>Top 8</th>
        }
        <th className="date" onClick={table.sort.bind(table, "date", "DESC")}>Date</th>
        { table.props.showLegalSeasons
            ? <th onClick={table.sort.bind(table, "season", "DESC")}>Season</th>
            : null
        }
    </tr>
);

const renderRow = (table, deck) => (
    <tr key={deck.id}>
        <td className="marginalia" dangerouslySetInnerHTML={{__html: deck.starsSafe}}></td>
        <td dangerouslySetInnerHTML={{__html: deck.colorsSafe}} ></td>
        <td className="deck-name"><a title={deck.decklist || null} href={deck.url}>{deck.name}</a></td>
        { table.props.hidePerson
            ? null
            : <td className="person"><a href={deck.personUrl} className="person">{deck.person}</a></td>
        }
        { table.props.showArchetype
            ? <td className="archetype"><a href={deck.archetypeUrl}>{deck.archetypeName}</a></td>
            : null
        }
        { table.props.hideSource
            ? null
            : <td className="source">
                { deck.competitionUrl
                    ? <a href={deck.competitionUrl}>{deck.sourceName}</a>
                    : <React.Fragment>{deck.sourceName}</React.Fragment>
                }
            </td>
        }
        <td className="record n">
            { deck.competitionUrl
                ? <a href={deck.competitionUrl}>{renderRecord(deck)}</a>
                : renderRecord(deck)
            }
        </td>
        { table.props.showOmw
            ? <td className="omw n">{deck.omw}</td>
            : null
        }
        { table.props.hideTop8
            ? null
            : <td className="top8 c">
                { deck.competitionUrl
                    ? <a href={deck.competitionUrl} dangerouslySetInnerHTML={{__html: deck.top8Safe}}></a>
                    : <span dangerouslySetInnerHTML={{__html: deck.top8Safe}}></span>
                }
            </td>
        }
        <td className="date">
            {deck.displayDate}
        </td>
        { table.props.showLegalSeasons
            ? <td dangerouslySetInnerHTML={{__html: deck.legalIcons}}></td>
            : null
        }
    </tr>
);

[...document.getElementsByClassName("decktable")].forEach((e) => {
    if (e !== null) {
        const table =
            <Table
                className="with-marginalia"
                endpoint="/api/decks/"
                renderHeaderRow={renderHeaderRow}
                renderRow={renderRow}
                showSearch={false}
                type="Deck"
                {...e.dataset}
            />;
        render(table, e);
    }
});
