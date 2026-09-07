/*global PD, Chart, ChartDataLabels, $ */

// Passing undefined as locale means "use browser locale" – https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat/NumberFormat
// eslint-disable-next-line no-undefined
const PD_PERCENTAGE_FORMATTER = new Intl.NumberFormat(undefined, { style: "percent", minimumSignificantDigits: 2, maximumSignificantDigits: 2 });

PD.formatPercentage = function (value) {
    return PD_PERCENTAGE_FORMATTER.format(value)
        // \D here is the locale-agnostic decimals separator.
        .replace(/(\D[0-9]*?)0+%$/, "$1%") // Get rid of trailing zeroes after the decimal separator.
        .replace(/\D%/, "%") // Clean up the scenario where we got rid of everything after the decimal separator and now have something like "4.%.
        .replace(/^0%$/, "0"); // Replace literal "0%" with "0" as zero is unitless.
};

PD.getChartColors = function() {
    const probe = document.createElement("span");
    probe.hidden = true;
    document.body.append(probe);
    const resolve = (property) => {
        probe.style.color = `var(${property})`;
        return getComputedStyle(probe).color;
    };
    const colors = {
        background: resolve("--highlight"),
        border: resolve("--light-border"),
        text: resolve("--text")
    };
    probe.remove();
    return colors;
};

PD.updateChartColors = function() {
    const colors = PD.getChartColors();
    Chart.defaults.borderColor = colors.border;
    Chart.defaults.color = colors.text;
    Object.values(Chart.instances).forEach((chart) => {
        chart.options.borderColor = colors.border;
        chart.options.color = colors.text;
        Object.values(chart.options.scales).forEach((scale) => {
            scale.border.color = colors.border;
            scale.grid.color = colors.border;
            scale.ticks.color = colors.text;
        });
        chart.data.datasets.forEach((dataset) => {
            dataset.backgroundColor = colors.background;
        });
        chart.update();
    });
};

PD.renderCharts = async function() {
    // Canvas text does not repaint when a web font finishes loading. Wait for
    // fonts before the first draw so a hard refresh cannot capture fallbacks.
    await document.fonts.ready;
    const colors = PD.getChartColors();
    // Note that changes made to Chart defaults here affect logs.pennydreadfulmagic.com/charts/ as well as decksite.
    Chart.register(ChartDataLabels);
    // Keep this hardcoded rather than waiting for window.onload (CSS and images loaded).
    // Should be kept in sync with CSS.
    Chart.defaults.font.family = 'symbols, main-text, Lato, "Helvetica Neue", Helvetica, Arial, sans-serif';
    Chart.defaults.font.size = "15px";
    Chart.defaults.plugins.datalabels.font.size = "15px";
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.tooltip.enabled = false;
    Chart.defaults.plugins.tooltip.titleAlign = "left";
    Chart.defaults.plugins.tooltip.bodyAlign = "right";
    Chart.defaults.plugins.datalabels.formatter = function (value) {
        return value || "";
    };
    Chart.defaults.plugins.datalabels.anchor = "end";
    Chart.defaults.plugins.datalabels.align = "end";
    Chart.defaults.plugins.tooltip.displayColors = false;
    Chart.defaults.plugins.colors.enabled = false;
    Chart.defaults.borderColor = colors.border;
    Chart.defaults.color = colors.text;
    $(".chart").each(function() {
        var type = $(this).data("type"),
            labels = $(this).data("labels"),
            series = $(this).data("series"),
            options = $(this).data("options"),
            ctx = this.getContext("2d");
        // These are our extension to Chart.js. We can't pass a callback from the HTML data attrs
        // so instead we intercept some magic values here to allow for a "percent" style and other
        // options. "percent" does actual exist as an undocumented option but it quite do what
        // we want so we override that behavior here.
        if (options.pd?.title?.style === "season") {
            options.plugins.tooltip.callbacks = options.plugins.tooltip.callbacks || {};
            options.plugins.tooltip.callbacks.title = (t) => "Season " + t[0].label;
        }
        for (const scale of Object.keys(options.scales)) {
            if (options.scales?.[scale]?.ticks?.format?.style === "percent") {
                options.scales[scale].ticks.callback = PD.formatPercentage;
                options.plugins.tooltip.callbacks = options.plugins.tooltip.callbacks || {};
                options.plugins.tooltip.callbacks.label = (v) => PD.formatPercentage(v.raw);
            }
        }
        if (options.pd?.tooltip?.additional_series) {
            const tooltip = options.pd.tooltip;
            options.plugins.tooltip.callbacks = options.plugins.tooltip.callbacks || {};
            options.plugins.tooltip.callbacks.label = (v) => {
                const additionalValue = tooltip.additional_series[v.dataIndex],
                    additionalText = additionalValue === null ? "N/A" : PD.formatPercentage(additionalValue);
                return [
                    tooltip.label + ": " + PD.formatPercentage(v.raw),
                    tooltip.additional_label + ": " + additionalText
                ];
            };
        }


        // eslint-disable-next-line no-new
        new Chart(ctx, {
            type,
            "data": {
                labels,
                datasets: [{ data: series, backgroundColor: colors.background }]
            },
            options
        });
    });
};
