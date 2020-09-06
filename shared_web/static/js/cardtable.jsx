/*global PD:true*/
import Axios from "axios";
import React from "react";
import { render } from "react-dom";

// eslint-disable-next-line no-unused-vars
class CardTable extends React.Component {

    constructor() {
        super();
        this.state = {
            cards: [],
            page: 0,
            pageSize: 20
        };
    }

    componentDidMount() {
        this.setState({"pageSize": this.props.pageSize}); // This will trigger a call to loadCards to get the initial data.
    }

    componentDidUpdate(prevProps, prevState) {
        for (const attr of ["pageSize", "page", "sortBy", "sortOrder"]) {
            if (prevState[attr] !== this.state[attr]) {
                this.loadCards();
                break;
            }
        }
    }

    loadCards() {
        const {page, pageSize, sortBy, sortOrder} = this.state;
        let deckType = "all";
        if (this.props.leagueOnly) {
            deckType = "league";
        } else if (this.props.tournamentOnly) {
            deckType = "tournament";
        }
        const params = {
            deckType,
            page,
            pageSize,
            "personId": this.props.personId,
            sortBy,
            sortOrder,
            "seasonId": this.props.seasonId
        };
        Axios.get("/api/cards2/", { params })
            .then(
                (response) => { this.setState({"cards": response.data.cards, "pages": response.data.pages}); PD.initTables(); },
                (error) => { this.setState({ error }); }
            );
    }

    // eslint-disable-next-line class-methods-use-this
    renderError(error) {
        return (
            <p className="error">Unable to load cards: {error}</p>
        );
    }

    render() {
        if (this.state.error) {
            return this.renderError(JSON.stringify(this.state.error));
        }
        const className = "live";
        const { cards } = this.state;
        this.renderCardRow = this.renderCardRow.bind(this);
        this.renderPagination = this.renderPagination.bind(this);
        const cardRows = cards.map(this.renderCardRow);
        const pagination = this.renderPagination();
        // Prevent content jumping by setting a min-height.
        document.getElementById("cardtable").style.minHeight = cards.length + "em";

        return (
            <React.Fragment>
                <table className={className}>
                    <thead>
                        <tr>
                            <th className="card" onClick={this.sort.bind(this, "name", "ASC")}>Card</th>
                            <th className="n num-decks" onClick={this.sort.bind(this, "numDecks", "ASC")}># Decks</th>
                            <th className="n card-record" onClick={this.sort.bind(this, "record", "DESC")}>Record</th>
                            <th className="n win-percent" onClick={this.sort.bind(this, "winPercent", "DESC")}>Win %</th>
                            <th className="n tournament-wins" onClick={this.sort.bind(this, "tournamentWins", "DESC")}>
                                <abbr title="Tournament wins">①</abbr>
                            </th>
                            <th className="n tournament-top-8s" onClick={this.sort.bind(this, "tournamentTop8s", "DESC")}>
                                <abbr title="Tournament Top 8s">⑧</abbr>
                            </th>
                            { this.props.tournamentOnly
                                ? null
                                : <th className="n perfect-runs" onClick={this.sort.bind(this, "perfectRuns", "DESC")}><abbr title="League 5-0 runs">5–0s</abbr></th>
                            }
                        </tr>
                    </thead>
                    <tbody>
                        {cardRows}
                    </tbody>
                </table>
                {pagination}
            </React.Fragment>
        );
    }

    renderCardRow(card) {
        return (
            <tr key={card.name} className="cardrow" data-cardname={card.name}>
                <td className="name">{this.renderCard(card)}</td>
                <td className="n">{card.numDecks}</td>
                <td className="n">{this.renderRecord(card)}</td>
                <td className="n">{this.renderWinPercent(card)}</td>
                <td className="n">
                    { card.tournamentWins > 0
                        ? card.tournamentWins
                        : ""
                    }
                </td>
                <td className="n">
                    { card.tournamentTop8s > 0
                        ? card.tournamentTop8s
                        : ""
                    }
                </td>
                {
                    this.props.tournamentOnly
                    ? null
                    : <td className="n">
                        {
                            card.perfectRuns > 0
                            ? card.perfectRuns
                            : ""
                        }
                    </td>
                }
            </tr>
        );
    }

    renderCard(card) {
        return (
            <React.Fragment>
                <a href={card.url} className="card">{card.name}</a>
                {
                    card.pdLegal
                    ? ""
                    : <span className="illegal"></span>
                }
            </React.Fragment>
        );

    }

    // eslint-disable-next-line class-methods-use-this
    renderRecord(card) {
        if (card.showRecord && card.wins + card.losses + card.draws > 0) {
            return card.wins + "–" + card.losses + (card.draws > 0 ? "–" + card.draws : "");
        }
        return "";
    }

    renderWinPercent(card) {
        if (card.showRecord) {
            return card.winPercent;
        }
    }

    renderPagination() {
        const { cards, page } = this.state;
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
                { cards.length < 20 && page === 0
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
            document.getElementById("cardtable").scrollIntoView();
        }
    }
}

const e = document.getElementById("cardtable");
if (e !== null) {
    const table =
        <CardTable
            archetypeId={e.dataset.archetypeId}
            cardName={e.dataset.cardName}
            competitionId={e.dataset.competitionId}
            pageSize={e.dataset.pageSize}
            personId={e.dataset.personId}
            seasonId={e.dataset.seasonId}
            showInteresting={e.dataset.showInteresting}
            tournamentOnly={e.dataset.tournamentOnly}
        />;
    render(table, e);
}
