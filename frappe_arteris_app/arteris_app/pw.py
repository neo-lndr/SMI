#!/usr/bin/env python3
"""
Teste mínimo e rápido do Playwright
"""

import asyncio
from playwright.async_api import async_playwright

async def minimal_test():
    print("🔗 Conectando ao Playwright...")
    
    async with async_playwright() as p:
        # Conectar
        browser = await p.chromium.connect("ws://playwright:3000/")
        print("✅ Conectado!")
        
        # Criar página
        page = await browser.new_page()
        print("📄 Página criada!")
        
        # Testar internet
        await page.goto("https://smi.arteris.com.br/capa_boletim?id=BM-CW44149-001")
        print("🌐 Página carregada!")
        
        # Verificar conteúdo
        content = await page.text_content("body")
        if "origin" in content:
            print("✅ Internet OK!")
        
        # Screenshot
        await page.screenshot(path="/tmp/test.png")
        print("📸 Screenshot salvo em /tmp/test.png")
        
        # Limpar
        await browser.close()
        print("🧹 Finalizado!")

if __name__ == "__main__":
    try:
        asyncio.run(minimal_test())
        print("🎉 SUCESSO!")
    except Exception as e:
        print(f"❌ ERRO: {e}")
        exit(1)