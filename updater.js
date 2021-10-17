import fetch from "node-fetch"
const progress = {
    "id": "01FGEWZ07EXCHP0CBFHT0CD3ZG",
    "indexes": [
        3, 4, 5, 0, 1, 2
    ],
    "config": {
        "timeout": 0,
        "progress": 0.0
    },
    "type": "progress"
}
const init = async () => {
    await fetch("http://localhost:8081/add_widget", {
        method: "post",
        Headers: { "content-type": "application/json" },
        body: JSON.stringify(
            { ...progress }
        )
    })
}
const updateProgress = async () => {
    const data = await fetch("http://localhost:8081/widget", {
        method: "post",
        Headers: { "content-type": "application/json" },
        body: JSON.stringify(
            { ...progress }
        )
    })
}
init()

setInterval(() => {
    if (progress.config.progress <= 1) {
        const now = new Date()
        const percent_of_day = now.getHours() / 24 + now.getMinutes() / 24 / 60 + now.getSeconds() / 25 / 60 / 60
        console.log(percent_of_day)
        progress.config.progress = percent_of_day
        updateProgress()

    }
}, 15000)
