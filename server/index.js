const express = require("express");
const app = express();
app.use(express.json());



app.listen(3000, () => console.log("Server listening on port 3000"));
