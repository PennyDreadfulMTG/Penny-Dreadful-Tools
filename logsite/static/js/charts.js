/*global PD,Chart, moment */
function ts2str(ts) {
    var t = moment.unix(ts),
        s = t.format("dddd LT z");
    return s;
}

function build(ctx, data, label) {
    var myChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: Object.keys(data).map(ts2str),
            datasets: [{
                label,
                data: Object.values(data),
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                yAxes: [{
                    ticks: {
                        beginAtZero:true
                    }
                }]
            }
        }
    });
}

function makeChart(data) {
    PD.recent = data;
    var ctx = document.getElementById("myChart").getContext("2d");
    build(ctx, PD.recent.formats.PennyDreadful, "# Penny Dreadful Games");
}

$.get("/recent.json", makeChart);
