/*global PD,Chart */
function make_chart(data) {
    PD.chart_data = data;
    var ctx = document.getElementById("myChart").getContext('2d');
    build(ctx, PD.chart_data.formats.PennyDreadful, '# Penny Dreadful Games');
};

function ts2str(ts) {
    var t = moment.unix(ts),
        s = t.format("dddd LT z");
    return s;
};

function build(ctx, data, label) {
    var myChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(data).map(ts2str),
            datasets: [{
                label: label,
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
};


$.get("/recent.json", make_chart);
