import {defineConfig} from '@playwright/test';
import chromium from '@sparticuz/chromium';
const sandbox=process.env.SANDBOX_CHROMIUM==='1';
export default defineConfig({testDir:'./tests',workers:1,timeout:60000,use:{baseURL:'http://localhost:5173',headless:true,launchOptions:sandbox?{args:chromium.args,executablePath:await chromium.executablePath()}:{}},reporter:'list'});
