/*global PD*/
import PropTypes from "prop-types";
import React from "react";


export const FriendlyTime = ({date}) => {
    if (!date || !date.datetime) {
        return date?.display ?? "";
    }
    return <time dateTime={date.datetime} title={PD.formatExactTimestamp(date.datetime)}>{date.display}</time>;
};

FriendlyTime.propTypes = {
    "date": PropTypes.shape({
        "datetime": PropTypes.string.isRequired,
        "display": PropTypes.string.isRequired,
    }),
};
