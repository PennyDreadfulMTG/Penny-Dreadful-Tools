/*global PD,Deckbox:true*/
import Axios from "axios";
import PropTypes from "prop-types";
import React from "react";
import { debounce } from "lodash";

/*

General React component with knowledge of pagination, sort order, page size, and many Magic and PD-specific properties such as "tournament only".

Use one of the child components, Table or Grid. To implement a new child component you need to implement render.

For properties see concrete uses in decktable, cardtable, metagamegrid, etc.

*/

// eslint-disable-next-line no-unused-vars
export class DataManager extends React.Component {
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
            Deckbox.load(this.state.page > 0);
        }
    }

    load() {
        const { page, pageSize, q, sortBy, sortOrder } = this.state;
        let deckType = "all";
        if (this.props.leagueOnly) {
            deckType = "league";
        } else if (this.props.tournamentOnly) {
            deckType = "tournament";
        }
        const params = {
            "achievementKey": this.props.achievementKey,
            "allLegal": this.props.allLegal,
            "archetypeId": this.props.archetypeId,
            "baseQuery": this.props.baseQuery,
            "cardName": this.props.cardName,
            "competitionId": this.props.competitionId,
            "competitionFlagId": this.props.competitionFlagId,
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

    preRender() {
        if (this.state.objects.length === 0 && !this.state.loadedOnce) {
            return { loading: true };
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

        return { loading: false, objects, pageSizeChanged, queryChanged };
    }

    preRenderPagination() {
        // Some of the look here stolen from https://material-ui.com/components/tables/.
        const { objects, page } = this.state;
        const start = objects.length === 0 ? 0 : page * this.state.pageSize + 1;
        const end = Math.min(start + this.state.pageSize - 1, this.state.total);
        const total = this.state.total;
        return { end, total }
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

// Most of these are PropTypes.string because they come (originally) from data-* on the HTML element so this isn't very good typechecking.
// It would be nice to check what they "really" are.
DataManager.propTypes = {
    "achievementKey": PropTypes.string,
    "activeRunsText": PropTypes.string,
    "allLegal": PropTypes.string,
    "archetypeId": PropTypes.string,
    "baseQuery": PropTypes.string,
    "cardName": PropTypes.string,
    "className": PropTypes.oneOf(["", "with-marginalia"]),
    "competitionId": PropTypes.string,
    "competitionFlagId": PropTypes.string,
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
