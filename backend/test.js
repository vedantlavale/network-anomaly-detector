
        const puppeteer = require('puppeteer');
        (async () => {
            try {
                const browser = await puppeteer.launch({headless: "new"});
                const page = await browser.newPage();
                await page.goto('https://example.com');
                await browser.close();
                console.log('Puppeteer test successful');
            } catch (error) {
                console.error('Puppeteer test failed:', error.message);
                process.exit(1);
            }
        })();
        