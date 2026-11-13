import {test,expect} from '@playwright/test';
import fs from 'node:fs';
const auth=JSON.parse(fs.readFileSync('../reports/browser-auth.json','utf8'));
test('authenticated workspace, live data, details, charts, filters and exports',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await page.getByLabel('Username',{exact:true}).fill(auth.username);
  await page.getByLabel('Password',{exact:true}).fill(auth.password);
  await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading',{name:'Your integrity overview'})).toBeVisible();
  await expect(page.locator('.stats')).toContainText('558,211');
  await page.getByRole('navigation').getByRole('button',{name:'Providers',exact:true}).click();
  await expect(page.getByText('Provider directory',{exact:true})).toBeVisible();
  await page.locator('tbody tr').first().click();
  await expect(page.getByText('Why did the model predict this risk?',{exact:true})).toBeVisible();
  await expect(page.locator('.contribution')).toHaveCount(12);
  await page.getByRole('navigation').getByRole('button',{name:'Claims',exact:true}).click();
  await page.locator('tbody tr').first().click();
  await expect(page.getByText('Hybrid risk analysis',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Re-run inference'}).click();
  await expect(page.getByText('Isolation Forest score',{exact:true})).toBeVisible();
  for(const label of ['Fraud detection','Provider analytics','Physician analytics','Explainable AI','Model performance','Reports']){
    await page.getByRole('navigation').getByRole('button',{name:label,exact:true}).click();
    await expect(page.locator('main h1')).toContainText(label);
    await expect(page.locator('.state')).toHaveCount(0,{timeout:30000});
  }
  const download=page.waitForEvent('download');
  await page.getByRole('button',{name:'Download CSV'}).first().click();
  expect((await download).suggestedFilename()).toBe('providers.csv');
  await page.getByRole('button',{name:'Toggle theme'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'Toggle menu'}).click();
  await expect(page.locator('.sidebar')).toHaveClass(/mobile-open/);
  expect(errors).toEqual([]);
});
