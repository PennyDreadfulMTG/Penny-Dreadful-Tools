/*global PD:true*/
import Axios from "axios";
import React from "react";
import { render } from "react-dom";

// eslint-disable-next-line no-unused-vars
class DeckTable extends React.Component {

    constructor() {
        super();
        this.state = {
            decks: [],
            page: 0,
            pageSize: 20,
            sortBy: "date",
            sortOrder: "DESC"
        };
    }

    componentDidMount() {
        this.setState({"pageSize": this.props.pageSize}); // This will trigger a call to loadDecks to get the initial data.
    }

    componentDidUpdate(prevProps, prevState) {
        for (const attr of ["pageSize", "page", "sortBy", "sortOrder"]) {
            if (prevState[attr] !== this.state[attr]) {
                this.loadDecks();
                break;
            }
        }
    }

    loadDecks() {
        const {page, pageSize, sortBy, sortOrder} = this.state;
        let deckType = "all";
        if (this.props.leagueOnly) {
            deckType = "league";
        } else if (this.props.tournamentOnly) {
            deckType = "tournament";
        }
        const params = {
            "archetypeId": this.props.archetypeId,
            "cardName": this.props.cardName,
            deckType,
            page,
            pageSize,
            "personId": this.props.personId,
            sortBy,
            sortOrder,
            "seasonId": this.props.seasonId
        };
        Axios.get("/api/decks/", { params })
            .then(
                (response) => { this.setState({"decks": response.data.decks, "pages": response.data.pages}); PD.initTables(); },
                (error) => { this.setState({ error }); }
            );
    }

    // eslint-disable-next-line class-methods-use-this
    renderError(error) {
        return (
            <p className="error">Unable to load decks: {error}</p>
        );
    }

    render() {
        if (this.state.error) {
            return this.renderError(JSON.stringify(this.state.error));
        }
        const className = "live with-marginalia";
        const { decks } = this.state;
        this.renderDeckRow = this.renderDeckRow.bind(this);
        this.renderPagination = this.renderPagination.bind(this);
        const deckRows = decks.map(this.renderDeckRow);
        const pagination = this.renderPagination();
        // Prevent content jumping by setting a min-height.
        document.getElementById("decktable").style.minHeight = decks.length + "em";
        return (
            <React.Fragment>
                <table className={className}>
                    <thead>
                        <tr>
                            <th className="marginalia" onClick={this.sort.bind(this, "marginalia", "ASC")}>⇅</th>
                            <th onClick={this.sort.bind(this, "colors", "ASC")}>Colors</th>
                            <th className="name" onClick={this.sort.bind(this, "name", "ASC")}>Name</th>
                            { this.props.hidePerson
                                ? null
                                : <th className="person" onClick={this.sort.bind(this, "person", "ASC")}>Person</th>
                            }
                            { this.props.showArchetype
                                ? <th className="archetype" onClick={this.sort.bind(this, "archetype", "ASC")}>Archetype</th>
                                : null
                            }
                            { this.props.hideSource
                                ? null
                                : <th className="source" onClick={this.sort.bind(this, "sourceName", "ASC")}>Source</th>
                            }
                            <th className="n record" onClick={this.sort.bind(this, "record", "DESC")}>Record</th>
                            { this.props.showOmw
                                ? <th className="omw" title="Opponent's Match Win" onClick={this.sort.bind(this, "omw", "DESC")}>OMW</th>
                                : null
                            }
                            { this.props.hideTop8
                                ? null
                                : <th className="c top8" onClick={this.sort.bind(this, "top8", "ASC")}>Top 8</th>
                            }
                            <th className="date" onClick={this.sort.bind(this, "date", "DESC")}>Date</th>
                            { this.props.showLegalSeasons
                                ? <th onClick={this.sort.bind(this, "season", "DESC")}>Season</th>
                                : null
                            }
                        </tr>
                    </thead>
                    <tbody>
                        { this.props.activeRunsText && this.state.page === 0
                            ? <tr>
                                <td className="marginalia"><span className="active" title="Active in the current league">⊕</span></td>
                                <td></td>
                                <td>{this.props.activeRunsText}</td>
                            </tr>
                            : null
                        }
                        {deckRows}
                    </tbody>
                </table>
                {pagination}
            </React.Fragment>
        );
    }

    renderDeckRow(deck) {
        return (
            <tr key={deck.id}>
                <td className="marginalia" dangerouslySetInnerHTML={{__html: deck.starsSafe}}></td>
                <td dangerouslySetInnerHTML={{__html: deck.colorsSafe}} ></td>
                <td className="name"><a title={deck.decklist || null} href={deck.url}>{deck.name}</a></td>
                { this.props.hidePerson
                    ? null
                    : <td className="person"><a href={deck.personUrl} className="person">{deck.person}</a></td>
                }
                { this.props.showArchetype
                    ? <td className="archetype"><a href={deck.archetypeUrl}>{deck.archetypeName}</a></td>
                    : null
                }
                { this.props.hideSource
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
                        ? <a href={deck.competitionUrl}>{this.renderRecord(deck)}</a>
                        : this.renderRecord(deck)
                    }
                </td>
                { this.props.showOmw
                    ? <td className="omw n">{deck.omw}</td>
                    : null
                }
                { this.props.hideTop8
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
                { this.props.showLegalSeasons
                    ? <td dangerouslySetInnerHTML={{__html: deck.legalIcons}}></td>
                    : null
                }
            </tr>
        );
    }

    // eslint-disable-next-line class-methods-use-this
    renderRecord(deck) {
        if (deck.showRecord && deck.wins + deck.losses + deck.draws > 0) {
            return deck.wins + "–" + deck.losses + (deck.draws ? "–" + deck.draws : "");
        }
        return "";
    }

    renderPagination() {
        const { decks, page } = this.state;
        return (
            <div className="pagination">
                <p className="pagination-links">
                    { this.state.page > 0
                        ? <a className="prev" onClick={this.movePage.bind(this, this.state.page - 1)}>← Previous Page</a>
                        : null
                    }
                    { this.state.page < this.state.pages
                        ? <a className="next" onClick={this.movePage.bind(this, this.state.page + 1)}>Next Page →</a>
                        : null
                    }
                </p>
                { decks.length < 20 && page === 0
                    ? null
                    : <p className="page-size-options">
                        <a className={"page-size" + (this.state.pageSize === 20 ? " selected" : "")} onClick={this.changePageSize.bind(this, 20)}>20</a>
                        <a className={"page-size" + (this.state.pageSize === 100 ? " selected" : "")} onClick={this.changePageSize.bind(this, 100)}>100</a>
                        per page
                    </p>
                }
            </div>
        );
    }

    movePage(page) {
        this.setState({ page });
    }

    sort(sortBy, sortOrder = "ASC") {
        if (this.state.sortBy === sortBy) {
            sortOrder = this.state.sortOrder === "ASC" ? "DESC" : "ASC";
        }
        this.setState({ sortBy, sortOrder, "page": 0 });
    }

    changePageSize(pageSize) {
        const gotShorter = pageSize < this.state.pageSize;
        this.setState({ pageSize, "page": 0 });
        if (gotShorter) {
            document.getElementById("decktable").scrollIntoView();
        }
    }
}

const e = document.getElementById("decktable");
if (e !== null) {
    const table =
        <DeckTable
            activeRunsText={e.dataset.activeRunsText}
            archetypeId={e.dataset.archetypeId}
            cardName={e.dataset.cardName}
            hidePerson={e.dataset.hidePerson}
            hidePerson={e.dataset.hidePerson}
            hideSource={e.dataset.hideSource}
            hideTop8={e.dataset.hideTop8}
            leagueOnly={e.dataset.leagueOnly}
            pageSize={e.dataset.pageSize}
            personId={e.dataset.personId}
            seasonId={e.dataset.seasonId}
            showArchetype={e.dataset.showArchetype}
            showLegalSeasons={e.dataset.showLegalSeasons}
            showOmw={e.dataset.showOmw}
            tournamentOnly={e.dataset.tournamentOnly}
        />;
    render(table, e);
}
