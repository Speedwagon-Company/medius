
async function test() {
    return new Promise(res => {
        res("aga")
    })
}

(async () => {
    console.log(await test())
})()