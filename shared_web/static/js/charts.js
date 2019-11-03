/*global PD,Chart, moment, $ */
var ctx = document.getElementById("pdChart").getContext("2d");

const ts2str = function(ts) {
    var t = moment.unix(ts),
        tz = moment.tz.guess(),
        s = t.tz(tz).format("dddd LT z");
    return s;
};

const build = function() {
    var data = PD.recent.formats.PennyDreadful;
    PD.Chart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: Object.keys(data).map(ts2str),
            datasets: [{
                label: "# Penny Dreadful Games",
                data: Object.values(data),
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                yAxes: [{
                    ticks: {
                        beginAtZero: true
                    }
                }]
            }
        }
    });
};

const makeChart = function(data) {
    PD.recent = data;
    build();
};

$.get("/recent.json", makeChart);
