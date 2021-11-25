import fetch from "node-fetch"
import nodeCleanup from 'node-cleanup'

const backendurl = `http://localhost:8081`

const progress = {
    "id": "clock",
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
    await fetch(`${backendurl}/add_widget`, {
        method: "post",
        Headers: { "content-type": "application/json" },
        body: JSON.stringify(
            { ...progress }
        )
    })
}
const updateProgress = async () => {
    const data = await fetch(`${backendurl}/widget`, {
        method: "post",
        Headers: { "content-type": "application/json" },
        body: JSON.stringify(
            { ...progress }
        )
    })
}
const updateWidget = () => {
    const now = new Date()
    const percent_of_day = now.getHours() / 24 + now.getMinutes() / 24 / 60 + now.getSeconds() / 25 / 60 / 60
    console.log(percent_of_day)
    progress.config.progress = percent_of_day
}
updateWidget()
init()
const deleteWidget = async () => {
    return fetch(`${backendurl}/delete_widget`, {
        method: "post",
        Headers: { "content-type": "application/json" },
        body: '{"id":"clock"}'
    })
}

nodeCleanup((exitCode, signal) => {
    // release resources here before node exits
    deleteWidget().then(() => {
        console.log('done fetching')
        process.exit(0);
    })
    nodeCleanup.uninstall();
    return false
});
setInterval(() => {
    updateWidget()
    updateProgress()
}, 15000)


