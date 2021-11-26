# Keyboard Led Control

I do talk more about this server in the video abuot connecting it to streamer bot for twitch notifications here https://www.youtube.com/watch?v=x9fZ-6AX4nM

run the server with
```bash
python server.py
```

then either setup your apps to handle notifications like with streamer bot

or run any of the example apps from the node-apps directory

to set them up run
```bash
cd node-apps
npm install
```

and then choose an app while inside the node-apps folder
```bash
npm run clock
```

currently used for twitch alerts and a background clock on my 6 key macro pad


# API Docs
server port is `8081`
### GET /widgets
shows a list of the currently displayed widgets

response:
```json
[
  {
    "id": "clock",
    "indexes": [
      3,
      4,
      5,
      0,
      1,
      2
    ],
    "config": {
      "timeout": 0,
      "progress": 0.9718055555555556
    },
    "type": "progress"
  }
]
```

### GET /notification
parameters
| Parameter | Explanation |
| --- | --- |
| h   | hue as number from 0 - 255 (0 being red 128 cyan)| 
| s   | saturation as number form 0 - 255 |
| v   | value (lightness) as number form 0 - 255 |
| timeout | timeout in seconds |
| indexes | indexes of the used LEDs separated by comma |

example query 
```
http://localhost:8081/notification?h=240&s=255&v=255&indexes=5,4&timeout=15
```
example response 
```json
{
  "success": true,
  "id": "01FNCD62EGBVFYCP23TB1FRC2Y"
}
```

### POST /delete_widget
deletes the widget with the supplied id
post request with json body and header "content-type": "application/json"

json body
```json
{  "id": "01FGEWZ07EXCHP0CBFHT0CD3ZG"}
```


### POST /add_widget
adds a widget to the notification stack

post request with json body and header "content-type": "application/json"

#### json body for a notification
| Parameter | Explanation |
| --- | --- |
| id | can be any string |
| indexes | indexes are an array of numbers|
| config.timeout | is a positive number in seconds (0 means no timeout)|
| config.color |is the hsv object with each value being 0-255|


```json
  {
    "id": "01FGEWZ07EXCHP0CBFHT0CD3ZG",
    "indexes": [
        0,1,2,3,4,5
    ],
    "config": {
        "timeout": 15.0,
        "color": {
            "h": 150,
            "s": 255,
            "v": 255
        }
    },
    "type": "notification"
  }
```

#### json body for a progress widget

| Parameter | Explanation |
| --- | --- |
| id | can be any string |
| indexes | indexes are an array of numbers|
| config.timeout | is a positive number in seconds (0 means no timeout)|
| config.progress | a number between 0-1 |


```json
  {
    "id": "01FGEWZ07EXCHP0CBFHT0CD3ZG",
    "indexes": [
      0,1,2,3,4,5
    ],
    "config": {
      "timeout": 0,
     "progress": 0.011199999999999998
    },
    "type": "progress"
  }
```
#### json body for a image widget
this can define multiple LEDs in separate colors
| Parameter | Explanation |
| --- | --- |
| id | can be any string |
| indexes | indexes are an array of numbers|
| config.timeout | is a positive number in seconds (0 means no timeout)|
| config.colors | an array of color objects each with hsv values from 0-255 , the first color gets applied to the first led in the `indexes` array and so on. so each led in the `indexes` array has its own color assigned and the array order of colors correspond to the indexes|

```json
  {
    "id": "01FGEWZ07EXCHP0CBFHT1CD3Z9",
    "indexes": [
      0,5
    ],
    "config": {
        "timeout": 31,
        "colors": [
            {
                "h": 255,
                "s": 255,
                "v": 255
            }, {
                "h": 182,
                "s": 255,
                "v": 255
            }
        ]
    },
    "type": "image"
  }
```

### POST /widget
update an existing widget identified by id

see above for examples on how to configure the widget data

post request with json body and header "content-type": "application/json"

```json
  {
    "id": "01FGEWZ07EXCHP0CBFHT0CD3ZG",
    "indexes": [
      3
    ],
    "config": {
      "timeout": 0,
     "progress": 0.04
    },
    "type": "progress"
  }
```
