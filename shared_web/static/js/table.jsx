import { DataManager } from "./datamanager";
import { Pagination } from "./pagination";
import PropTypes from "prop-types";
import React from "react";

/*

General React table using DataManager.

To be passed a renderHeaderRow(table) and a renderRow(table, object) that return a <tr> to populate the table with.

For properties see concrete uses in decktable, cardtable, etc.

*/

export class Table extends DataManager {
    render() {
        const { loading, objects, pageSizeChanged, queryChanged } = super.preRender();
        const className = ("live " + (this.props.className ?? "")).trim();
        const skeletonClassName = loading ? ` table-skeleton${this.props.showSeasonIcon ? " table-skeleton-season-icons" : ""}` : "";
        const containerClassName = (className + skeletonClassName).trim();
        const headerRow = this.props.renderHeaderRow(this);
        const rows = loading ? this.renderSkeletonRows(headerRow) : objects.map((o) => this.props.renderRow(this, o));

        return (
            <div ref={this.divRef} aria-busy={loading} className={containerClassName}>
                <div className="table-header">
                    { loading
                        ? <span className="table-loading" role="status"><span className="spinner"></span> <span>Loading…</span></span>
                        : <React.Fragment>
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
                        </React.Fragment>
                    }
                </div>
                <table aria-hidden={loading} className={className}>
                    <thead>
                        {headerRow}
                    </thead>
                    <tbody>
                        { !loading && this.props.activeRunsText && this.state.page === 0
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
                { loading
                    ? <div aria-hidden="true" className="pagination skeleton-pagination"></div>
                    : this.renderPagination()
                }
            </div>
        );
    }

    renderSkeletonRows(headerRow) {
        const cells = React.Children.toArray(headerRow.props.children);
        const rowCount = this.state.pageSize + (this.props.activeRunsText ? 1 : 0);
        return Array.from({ length: rowCount }, (_value, rowIndex) => (
            <tr className="skeleton-row" key={rowIndex}>
                {cells.map((cell, cellIndex) => (
                    <td className={cell.props.className} key={cellIndex}>
                        <span className="skeleton-cell"></span>
                    </td>
                ))}
            </tr>
        ));
    }

    renderPagination() {
        return <Pagination {...super.preRenderPagination()} page={this.state.page} onPageChange={this.movePage.bind(this)}/>;
    }
}

export const renderRecord = (object) => {
    if (object.showRecord && object.wins + object.losses + object.draws > 0) {
        return object.wins.toLocaleString() + "–" + object.losses.toLocaleString() + (object.draws > 0 ? "–" + object.draws.toLocaleString() : "");
    }
    return "";
};

export const renderWinPercent = (object) => {
    if (object.showRecord && Number.isFinite(object.winPercent)) {
        return object.winPercent.toLocaleString([], {minimumFractionDigits: 1, maximumFractionDigits: 1});
    }
    return "";
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
    "className": PropTypes.oneOf(["", "with-marginalia"]),
    "renderHeaderRow": PropTypes.func.isRequired,
    "renderRow": PropTypes.func.isRequired
};
