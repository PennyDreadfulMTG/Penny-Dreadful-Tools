/*global PD,Deckbox:true*/
import Axios from "axios";
import PropTypes from "prop-types";
import React from "react";
import { debounce } from "lodash";

/*

General React table with knowledge of pagination, sort order, page size, and many Magic and PD-specific properties such as "tournament only".

To be passed a renderHeaderRow(table) and a renderRow(table, object) that return a <tr> to populate the table with.

For properties see concrete uses in decktable, cardtable, etc.

*/

// eslint-disable-next-line no-unused-vars
export class Table extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            error: "",
            loadedOnce: false,
            message: "",
            objects: [],
            page: 0,
            pageSize: parseInt(props.pageSize, 10),
            q: ""
        };
        this.debouncedLoad = debounce(this.load, 250);
        this.divRef = React.createRef();
    }

    componentDidMount() {
        this.load();
    }

    componentDidUpdate(prevProps, prevState) {
        for (const attr of ["pageSize", "page", "sortBy", "sortOrder"]) {
            if (prevState[attr] !== this.state[attr]) {
                this.load();
                break;
            }
        }
        if (this.props.reloadCards && typeof Deckbox !== "undefined") {
            Deckbox.load();
        }
    }

    load() {
        const {page, pageSize, q, sortBy, sortOrder} = this.state;
        let deckType = "all";
        if (this.props.leagueOnly) {
            deckType = "league";
        } else if (this.props.tournamentOnly) {
            deckType = "tournament";
        }
        const params = {
            "achievementKey": this.props.achievementKey,
            "archetypeId": this.props.archetypeId,
            "cardName": this.props.cardName,
            "competitionId": this.props.competitionId,
            "competitionSeriesId": this.props.competitionSeriesId,
            deckType,
            page,
            pageSize,
            "personId": this.props.personId,
            q,
            sortBy,
            sortOrder,
            "seasonId": this.props.seasonId
        };
        Axios.get(this.props.endpoint, { params })
            .then(
                (response) => {
                    if (params.q === this.state.q) { // Don't update the table if this isn't the latest query.
                        this.setState({"objects": response.data.objects, "total": response.data.total, "error": "", "message": response.data.message, "loadedOnce": true}); PD.initTables();
                    }
                },
                (error) => { this.setState({"objects": [], "total": 0,  "error": error.message, "message": "", "loadedOnce": true }); }
            );
    }

    render() {
        if (this.state.objects.length === 0 && !this.state.loadedOnce) {
            return <div className="loading"><span className="spinner"></span> <span className="text">Loading…</span></div>;
        }
        const { objects } = this.state;
        const pageSizeChanged = (e) => {
            if (this.state.pageSize === e.target.value) {
                return;
            }
            this.setState({"pageSize": parseInt(e.target.value, 10), "page": 0});
        };
        const queryChanged = (e) => {
            if (this.state.q === e.target.value) {
                return;
            }
            this.setState({"q": e.target.value, "page": 0});
            this.debouncedLoad.apply(this);
        };
        const rows = objects.map((o) => this.props.renderRow(this, o));
        const className = ("live " + this.props.className).trim();

        return (
            <div ref={this.divRef} className={className}>
                <div className="table-header">
                    <span>
                        { this.props.showSearch
                            ? <form className="inline" onSubmit={(e) => { e.preventDefault(); }}>
                                <input className="name" placeholder={this.props.searchPrompt} type="text" onChange={queryChanged.bind(this)} value={this.state.q}/>
                            </form>
                            : null
                        }
                    </span>
                    { this.state.error
                        ? <span className="message error" title={this.state.error}>{this.state.error}</span>
                        : null
                    }
                    { this.state.message
                        ? <span className="message" title={this.state.message}>{this.state.message}</span>
                        : null
                    }
                    <span>
                        { this.state.total > 20
                            ? <form className="inline" onSubmit={(e) => { e.preventDefault(); }}>
                                <select className="page-size" value={this.state.pageSize} onChange={pageSizeChanged.bind(this)}>
                                    <option value="20">20</option>
                                    <option value="100">100</option>
                                </select>
                            </form>
                            : null
                        }
                    </span>
                </div>
                <table className={className}>
                    <thead>
                        {this.props.renderHeaderRow(this)}
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
                        {rows}
                    </tbody>
                </table>
                {this.renderPagination()}
            </div>
        );
    }

    renderPagination() {
        // Some of the look here stolen from https://material-ui.com/components/tables/.
        const { objects, page } = this.state;
        const start = objects.length === 0 ? 0 : page * this.state.pageSize + 1;
        const end = Math.min(start + this.state.pageSize - 1, this.state.total);
        const total = this.state.total;
        return (
            <div className="pagination">
                <span className="pages section">
                    {start}-{end} of {total}
                </span>
                <span className="links section">
                    { this.state.page > 0
                        ? <a className="prev paginate" onClick={this.movePage.bind(this, this.state.page - 1)}>←</a>
                        : <span className="inactive prev paginate">←</span>
                    }
                    { end < this.state.total
                        ? <a className="next paginate" onClick={this.movePage.bind(this, this.state.page + 1)}>→</a>
                        : <span className="inactive next paginate">→</span>
                    }
                </span>
            </div>
        );
    }

    movePage(page) {
        this.setState({ page });
        this.divRef.current.scrollIntoView();
    }

    sort(sortBy, sortOrder = "ASC") {
        if (this.state.sortBy === sortBy) {
            sortOrder = this.state.sortOrder === "ASC" ? "DESC" : "ASC";
        }
        this.setState({ sortBy, sortOrder, "page": 0 });
    }
}

export const renderRecord = (object) => {
    if (object.showRecord && object.wins + object.losses + object.draws > 0) {
        return object.wins + "–" + object.losses + (object.draws > 0 ? "–" + object.draws : "");
    }
    return "";
};

export const renderWinPercent = (object) => {
    if (object.showRecord) {
        return object.winPercent;
    }
};

export const renderCard = (card) => (
    <React.Fragment>
        <a href={card.url} className={"card" +  (card.interestingness ? " interesting interestingness-" + card.interestingness : "")}>{card.name}</a>
        { card.pdLegal
            ? ""
            : <span className="illegal"></span>
        }
    </React.Fragment>
);

// Most of these are PropTypes.string because they come (originally) from data-* on the HTML element so this isn't very good typechecking.
// It would be nice to check what they "really" are.
Table.propTypes = {
    "achievementKey": PropTypes.string,
    "activeRunsText": PropTypes.string,
    "archetypeId": PropTypes.string,
    "cardName": PropTypes.string,
    "className": PropTypes.oneOf(["", "with-marginalia"]),
    "competitionId": PropTypes.string,
    "competitionSeriesId": PropTypes.string,
    "endpoint": PropTypes.string.isRequired,
    "hidePerson": PropTypes.string,
    "hideSource": PropTypes.string,
    "hideTop8": PropTypes.string,
    "leagueOnly": PropTypes.string,
    "pageSize": PropTypes.string.isRequired,
    "personId": PropTypes.string,
    "reloadCards": PropTypes.bool,
    "renderHeaderRow": PropTypes.func.isRequired,
    "renderRow": PropTypes.func.isRequired,
    "searchPrompt": PropTypes.string,
    "seasonId": PropTypes.string,
    "showArchetype": PropTypes.string,
    "showSeasonIcon": PropTypes.string,
    "showOmw": PropTypes.string,
    "showSearch": PropTypes.bool,
    "tournamentOnly": PropTypes.string
};
