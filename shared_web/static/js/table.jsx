import { DataManager } from "./datamanager";
import PropTypes from "prop-types";
import React from "react";

/*

General React table using DataManager.

To be passed a renderHeaderRow(table) and a renderRow(table, object) that return a <tr> to populate the table with.

For properties see concrete uses in decktable, cardtable, etc.

*/

// eslint-disable-next-line no-unused-vars
export class Table extends DataManager {
    render() {
        const { loading, objects, pageSizeChanged, queryChanged } = super.preRender();
        if (loading) {
            return <div className="loading"><span className="spinner"></span> <span className="text">Loading…</span></div>;
        }

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
        const { start, end, total } = super.preRenderPagination();
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
        <a href={card.url} className={`card${card.firstLegalThisSeason ? " new" : ""}`}>{card.name}</a>
        { card.pdLegal
            ? ""
            : <span className="illegal"></span>
        }
    </React.Fragment>
);

Table.propTypes = {
    "renderHeaderRow": PropTypes.func.isRequired,
    "renderRow": PropTypes.func.isRequired
};
