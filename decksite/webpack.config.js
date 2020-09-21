/* eslint-disable */
const webpack = require("webpack");
const config = {
    entry: [
        __dirname + "/../shared_web/static/js/cardtable.jsx",
        __dirname + "/../shared_web/static/js/decktable.jsx"
    ],
    output: {
        path: __dirname + "/../shared_web/static//dist",
        filename: "bundle.js"
    },
    resolve: {
        extensions: [".js", ".jsx", ".css"]
    },
    module: {
        rules: [{
            test: /\.jsx?/,
            exclude: /node_modules/,
            use: "babel-loader"
        }, {
            test: /\.css$/,
            exclude: /node_modules/,
            loaders: ["style-loader", "css-loader"]
        }]
    }
};
module.exports = config;
