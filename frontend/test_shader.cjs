const puppeteer = require('puppeteer');

(async () => {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();

    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));

    await page.goto('http://localhost:8080/');
    await page.waitForTimeout(3000);
    await browser.close();
})();
