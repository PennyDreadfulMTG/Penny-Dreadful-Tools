/*global PD:true*/
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
            objects: [],
            page: 0,
            pageSize: props.pageSize,
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
            "archetypeId": this.props.archetypeId,
            "cardName": this.props.cardName,
            "competitionId": this.props.competitionId,
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
                (response) => { this.setState({"objects": response.data.objects, "pages": response.data.pages}); PD.initTables(); },
                (error) => { this.setState({ error }); }
            );
    }

    // eslint-disable-next-line class-methods-use-this
    renderError(error) {
        return (
            <p className="error">Unable to load: {error}</p>
        );
    }

    render() {
        if (this.state.error) {
            return this.renderError(JSON.stringify(this.state.error));
        }
        const { objects } = this.state;
        const queryChanged = (e) => {
            if (this.state.q === e.target.value) {
                return;
            }
            this.setState({q: e.target.value, "page": 0});
            this.debouncedLoad.apply(this);
        };
        const rows = objects.map((o) => this.props.renderRow(this, o));
        const className = ("live " + this.props.className).trim();

        return (
            <div ref={this.divRef} className={className} style={{ minHeight: objects.lenght + "em" }}> {/* Prevent content jumping by setting a min-height. */}
                { this.props.showSearch
                    ? <form className="inline" onSubmit={(e) => { e.preventDefault(); }}>
                        <input className="name" placeholder={this.props.type + " name"} type="text" onChange={queryChanged.bind(this)} value={this.state.q}/>
                    </form>
                    : null
                }
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
        const { objects, page } = this.state;
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
                { objects.length < 20 && page === 0
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
            this.divRef.current.scrollIntoView();
        }
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

// Most of these are PropTypes.string because they come (originally) from data-* on the HTML element so this isn't very good typechecking.
// It would be nice to check what they "really" are.
Table.propTypes = {
    "activeRunsText": PropTypes.string,
    "archetypeId": PropTypes.string,
    "cardName": PropTypes.string,
    "className": PropTypes.oneOf(["", "with-marginalia"]),
    "competitionId": PropTypes.string,
    "endpoint": PropTypes.string.isRequired,
    "hidePerson": PropTypes.string,
    "hideSource": PropTypes.string,
    "hideTop8": PropTypes.string,
    "leagueOnly": PropTypes.string,
    "pageSize": PropTypes.string.isRequired,
    "personId": PropTypes.string,
    "renderHeaderRow": PropTypes.func.isRequired,
    "renderRow": PropTypes.func.isRequired,
    "seasonId": PropTypes.string.isRequired,
    "showArchetype": PropTypes.string,
    "showLegalSeasons": PropTypes.string,
    "showOmw": PropTypes.string,
    "showSearch": PropTypes.bool,
    "tournamentOnly": PropTypes.string,
    "type": PropTypes.oneOf(["Card", "Deck", "Person"]).isRequired
};
