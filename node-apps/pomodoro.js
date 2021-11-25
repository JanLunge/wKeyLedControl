import fetch from "node-fetch"
const breaktime = 5 * 60
const worktime = 30 * 60
const timer = {
    "id": "01FGEWZ07EXCHX0CBFHT0CD3ZG",
    "indexes": [
        3, 4, 5, 0, 1, 2
    ],
    "config": {
        "color": {
            "h": 180,
            "s": 255,
            "v": 255
        },
        "timeout": breaktime,
    },
    "type": "notification"
}
const init = async () => {
    await fetch("http://localhost:8080/add_widget", {
        method: "post",
        Headers: { "content-type": "application/json" },
        body: JSON.stringify(
            { ...timer }
        )
    })
}

        init()
setInterval(() => {
        init()
}, (worktime+breaktime)*1000)
