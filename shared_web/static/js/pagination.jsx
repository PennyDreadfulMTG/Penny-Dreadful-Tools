import PropTypes from "prop-types";
import React from "react";

const PageIcon = ({ type }) => {
    const paths = {
        first: "M17 6l-6 6 6 6M7 6v12",
        last: "M7 6l6 6-6 6M17 6v12",
        next: "M9 6l6 6-6 6",
        previous: "M15 6l-6 6 6 6"
    };
    return (
        <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24">
            <path d={paths[type]} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"/>
        </svg>
    );
};

PageIcon.propTypes = {
    "type": PropTypes.oneOf(["first", "last", "next", "previous"]).isRequired
};

const PageButton = ({ disabled, label, onClick, type }) => (
    <button aria-label={label} className={`paginate ${type}`} disabled={disabled} title={label} type="button" onClick={onClick}>
        <PageIcon type={type}/>
    </button>
);

PageButton.propTypes = {
    "disabled": PropTypes.bool.isRequired,
    "label": PropTypes.string.isRequired,
    "onClick": PropTypes.func.isRequired,
    "type": PropTypes.oneOf(["first", "last", "next", "previous"]).isRequired
};

export const Pagination = ({ end, onPageChange, page, pageCount, pageNumber, start, total }) => {
    const firstPage = 0;
    const lastPage = pageCount - 1;
    return (
        <div aria-label="Pagination" className="pagination" role="navigation">
            <span className="pages section">
                {start.toLocaleString()}–{end.toLocaleString()} of {total.toLocaleString()}
            </span>
            <span aria-live="polite" className="page-number section">
                Page {pageNumber.toLocaleString()} of {pageCount.toLocaleString()}
            </span>
            <span className="links section">
                <PageButton disabled={page === firstPage} label="First page" type="first" onClick={() => onPageChange(firstPage)}/>
                <PageButton disabled={page === firstPage} label="Previous page" type="previous" onClick={() => onPageChange(page - 1)}/>
                <PageButton disabled={page === lastPage || lastPage < firstPage} label="Next page" type="next" onClick={() => onPageChange(page + 1)}/>
                <PageButton disabled={page === lastPage || lastPage < firstPage} label="Last page" type="last" onClick={() => onPageChange(lastPage)}/>
            </span>
        </div>
    );
};

Pagination.propTypes = {
    "end": PropTypes.number.isRequired,
    "onPageChange": PropTypes.func.isRequired,
    "page": PropTypes.number.isRequired,
    "pageCount": PropTypes.number.isRequired,
    "pageNumber": PropTypes.number.isRequired,
    "start": PropTypes.number.isRequired,
    "total": PropTypes.number.isRequired
};
