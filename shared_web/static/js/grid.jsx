import { DataManager } from "./datamanager";
import PropTypes from "prop-types";
import React from "react";

/*

General React grid using DataManager.

To be passed a renderItem(grid, item) that returns a <div> to populate the grid with.

For properties see concrete uses in metagamegrid.

*/

const STORAGE_KEY = "metagame-sort";

export class Grid extends DataManager {
    constructor(props) {
        super(props);
        try {
            const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
            if (stored) {
                if (stored.sortBy) this.state.sortBy = stored.sortBy;
                if (stored.sortOrder) this.state.sortOrder = stored.sortOrder;
            }
        } catch { /* ignore corrupt storage */ }
    }

    sort(sortBy, sortOrder = "AUTO") {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ sortBy, sortOrder }));
        } catch { /* ignore storage errors */ }
        this.setState({ sortBy, sortOrder, "page": 0 });
    }

    render() {
        const { loading, objects, queryChanged } = super.preRender();
        if (loading) {
            return <div className="loading"><span className="spinner"></span> <span className="text">Loading…</span></div>;
        }

        const tiles = objects.map((o) => this.props.renderItem(this, o));
        const className = this.props.className.trim();

        return (
            <div ref={this.divRef} className="data-manager-grid">
                <div className="grid-header">{/* we don't use this class so don't have it? */}{/* We don't use this div actually but should? */}
                    { this.props.showSearch
                        ? <span>
                            <form className="inline" onSubmit={(e) => { e.preventDefault(); }}>
                                <input className="name" placeholder={this.props.searchPrompt} type="text" onChange={queryChanged.bind(this)} value={this.state.q}/>
                            </form>
                        </span>
                        : null
                    }
                    { this.props.renderSort
                        ? <span className="sort">
                            {this.props.renderSort(this)}
                        </span>
                        : null
                    }
                    { this.state.error
                        ? <span className="message error" title={this.state.error}>{this.state.error}</span>
                        : null
                    }
                    { this.state.message
                        ? <span className="message" title={this.state.message}>{this.state.message}</span>
                        : null
                    }
                </div>
                <div className={className}>
                    {tiles}
                </div>
                {this.renderPagination()}
            </div>
        );
    }

    renderPagination() {
        const { start, end, pageCount, pageNumber, total } = super.preRenderPagination();
        const firstPage = 0;
        const lastPage = pageCount - 1;
        return (
            <div className="pagination">
                <span className="pages section">
                    {start}-{end} of {total}
                </span>
                <span className="links section">
                    { this.state.page > firstPage
                        ? <a aria-label="First page" className="first paginate" title="First page" onClick={this.movePage.bind(this, firstPage)}>⇤</a>
                        : <span aria-label="First page" className="inactive first paginate" title="First page">⇤</span>
                    }
                    { this.state.page > 0
                        ? <a aria-label="Previous page" className="prev paginate" title="Previous page" onClick={this.movePage.bind(this, this.state.page - 1)}>←</a>
                        : <span aria-label="Previous page" className="inactive prev paginate" title="Previous page">←</span>
                    }
                    <span className="page-number">Page {pageNumber} of {pageCount}</span>
                    { end < this.state.total
                        ? <a aria-label="Next page" className="next paginate" title="Next page" onClick={this.movePage.bind(this, this.state.page + 1)}>→</a>
                        : <span aria-label="Next page" className="inactive next paginate" title="Next page">→</span>
                    }
                    { this.state.page < lastPage
                        ? <a aria-label="Last page" className="last paginate" title="Last page" onClick={this.movePage.bind(this, lastPage)}>⇥</a>
                        : <span aria-label="Last page" className="inactive last paginate" title="Last page">⇥</span>
                    }
                </span>
            </div>
        );
    }
}

Grid.propTypes = {
    "className": PropTypes.oneOf(["", "metagame-grid"]),
    "renderSort": PropTypes.func
};
