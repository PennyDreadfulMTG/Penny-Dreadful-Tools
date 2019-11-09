/* eslint-disable */
const webpack = require("webpack");
const config = {
    entry: __dirname + "/../shared_web/static/js/index.jsx",
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
