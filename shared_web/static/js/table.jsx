/*global PD:true*/
import Axios from "axios";
import PropTypes from 'prop-types';
import React from "react";
import { debounce } from "lodash";
import { render } from "react-dom";

/*

General React table with knowledge of pagination, sort order, page size, and many Magic and PD-specific properties such as "tournament only".

To be passed a renderHeaderRow(table) and a renderRow(table, object) that return a <tr> to populate the table with.

For properties see concrete uses in decktable, cardtable, etc.

*/

// eslint-disable-next-line no-unused-vars
export default class Table extends React.Component {

    constructor() {
        super();
        this.state = {
            objects: [],
            page: 0,
            pageSize: 20,
            q: ""
        };
        this.debouncedLoad = debounce(this.load, 250);
    }

    componentDidMount() {
        this.setState({"pageSize": this.props.pageSize}); // This will trigger a call to load to get the initial data.
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
                (response) => { this.setState({"objects": response.data.objects, "pages": response.data.pages}); PD.initTables(); }, // BAKERT need to change what we return to be objects not cards?
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
        const className = "live";
        const { objects } = this.state;
        const queryChanged = (e) => {
            if (this.state.q === e.target.value) {
                return;
            }
            this.setState({q: e.target.value, "page": 0});
            this.debouncedLoad.apply(this);
        };
        this.renderPagination = this.renderPagination.bind(this); // BAKERT this is just bizarre. Why?
        const rows = objects.map(o => this.props.renderRow(this, o));
        const pagination = this.renderPagination();

        return (
            <div ref="table" className={className} style={{ minHeight: objects.lenght + "em" }}> {/* Prevent content jumping by setting a min-height. */}
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
                        {rows}
                    </tbody>
                </table>
                {pagination}
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
        console.log(sortBy + ' ' + sortOrder);
        if (this.state.sortBy === sortBy) {
            sortOrder = this.state.sortOrder === "ASC" ? "DESC" : "ASC";
        }
        this.setState({ sortBy, sortOrder, "page": 0 });
    }

    changePageSize(pageSize) {
        const gotShorter = pageSize < this.state.pageSize;
        this.setState({ pageSize, "page": 0 });
        if (gotShorter) {
            this.refs.table.scrollIntoView();
        }
    }
}

Table.propTypes = {
    "activeRunsText": PropTypes.string,
    "archetypeId": PropTypes.int,
    "cardName": PropTypes.string,
    "competitionId": PropTypes.int,
    "hidePerson": PropTypes.bool,
    "hideSource": PropTypes.bool,
    "hideTop8": PropTypes.bool,
    "leagueOnly": PropTypes.bool,
    "pageSize": PropTypes.int,
    "personId": PropTypes.int,
    "seasonId": PropTypes.int,
    "showArchetype": PropTypes.bool,
    "showLegalSeasons": PropTypes.bool,
    "showOmw": PropTypes.bool,
    "showSearch": PropTypes.bool,
    "tournamentOnly": PropTypes.bool,
}
