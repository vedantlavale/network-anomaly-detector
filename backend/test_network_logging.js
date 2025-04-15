const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

(async () => {
  console.log('Starting Puppeteer test with network logging...');
  const browser = await puppeteer.launch({headless: "new"});
  const page = await browser.newPage();
  
  // Track all network requests
  const requests = [];
  
  page.on('request', request => {
    requests.push({
      url: request.url(),
      method: request.method(),
      resourceType: request.resourceType()
    });
    console.log(`Request: ${request.method()} ${request.url()}`);
  });
  
  console.log('Navigating to example.com...');
  await page.goto('https://example.com', {waitUntil: 'networkidle0'});
  console.log('Navigation complete.');
  
  // Save logs
  const dataDir = path.join(__dirname, '../data');
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  
  const outputPath = path.join(dataDir, 'test_network_logs.json');
  fs.writeFileSync(outputPath, JSON.stringify(requests, null, 2));
  console.log(`Saved ${requests.length} network logs to ${outputPath}`);
  
  await browser.close();
  console.log('Test complete!');
})();