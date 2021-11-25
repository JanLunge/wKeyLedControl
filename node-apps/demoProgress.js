import fetch from "node-fetch"
const progress = {
    "id": "01FGEWZ57EXCHP0CBFHT0CD3ZG",
    "indexes": [
        3, 4, 5, 0, 1, 2
    ],
    "config": {
        "timeout": 0,
        "progress": 0.0
    },
    "type": "progress"
}
const start = new Date()

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
    const now = new Date()
    const duration = 3
    const value = (((now - start)/1000)%duration)/duration
        progress.config.progress = value
         updateProgress()

}, 20)
