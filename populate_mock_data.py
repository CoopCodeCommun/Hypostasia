
import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')
django.setup()

from core.models import Page, TextBlock, Argument

SCENARIOS = [
    {
        "topic": "Nuclear Energy",
        "url": "https://energy-debate.com/nuclear-power",
        "html": "<html><body><article><p>Nuclear energy is dense.</p><p>But the waste is dangerous.</p></article></body></html>",
        "readability": "<p>Nuclear energy is dense.</p><p>But the waste is dangerous.</p>",
        "arguments": [
            {
                "text": "Nuclear energy is dense.",
                "summary": "High energy density allows for massive power generation with small footprint.",
                "stance": "pour"
            },
            {
                "text": "But the waste is dangerous.",
                "summary": "Radioactive waste poses long-term storage and safety challenges.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "Artificial Intelligence",
        "url": "https://tech-future.org/ai-risks",
        "html": "<html>...</html>",
        "readability": "<p>AI can automate boring tasks.</p><p>It might replace jobs.</p>",
        "arguments": [
            {
                "text": "AI can automate boring tasks.",
                "summary": "AI increases productivity by handling repetitive tasks.",
                "stance": "pour"
            },
            {
                "text": "It might replace jobs.",
                "summary": "Widespread AI adoption could lead to significant unemployment.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "Remote Work",
        "url": "https://work-life.com/remote",
        "html": "<html>...</html>",
        "readability": "<p>No commute saves time.</p><p>Teams feel isolated.</p>",
        "arguments": [
            {
                "text": "No commute saves time.",
                "summary": "Employees save hours daily by not commuting.",
                "stance": "pour"
            },
            {
                "text": "Teams feel isolated.",
                "summary": "Lack of face-to-face interaction weakens team cohesion.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "Universal Basic Income",
        "url": "https://economics-daily.net/ubi",
        "html": "<html>...</html>",
        "readability": "<p>UBI reduces poverty.</p><p>It costs too much.</p>",
        "arguments": [
            {
                "text": "UBI reduces poverty.",
                "summary": "Providing a safety net eliminates extreme poverty effectively.",
                "stance": "pour"
            },
            {
                "text": "It costs too much.",
                "summary": "Funding UBI requires massive tax increases or printing money.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "Electric Vehicles",
        "url": "https://green-drive.com/evs",
        "html": "<html>...</html>",
        "readability": "<p>No tailpipe emissions.</p><p>Batteries need mining.</p>",
        "arguments": [
            {
                "text": "No tailpipe emissions.",
                "summary": "EVs improve local air quality significantly.",
                "stance": "pour"
            },
            {
                "text": "Batteries need mining.",
                "summary": "Extraction of lithium and cobalt has high environmental costs.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "Social Media",
        "url": "https://social-impact.org/media",
        "html": "<html>...</html>",
        "readability": "<p>Connects people globally.</p><p>Causes depression.</p>",
        "arguments": [
            {
                "text": "Connects people globally.",
                "summary": "Allows instant communication across borders and cultures.",
                "stance": "pour"
            },
            {
                "text": "Causes depression.",
                "summary": "Algorithmic feeds amplify negative emotions and comparison.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "Space Exploration",
        "url": "https://cosmos-news.com/space",
        "html": "<html>...</html>",
        "readability": "<p>Inspires innovation.</p><p>Better spend money on Earth.</p>",
        "arguments": [
            {
                "text": "Inspires innovation.",
                "summary": "Space tech leads to spin-offs like GPS and medical imaging.",
                "stance": "pour"
            },
            {
                "text": "Better spend money on Earth.",
                "summary": "Funds should address poverty and climate change first.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "GMOs",
        "url": "https://food-science.net/gmos",
        "html": "<html>...</html>",
        "readability": "<p>Higher crop yields.</p><p>Unknown long term effects.</p>",
        "arguments": [
            {
                "text": "Higher crop yields.",
                "summary": "Genetically modified crops resist pests and drought better.",
                "stance": "pour"
            },
            {
                "text": "Unknown long term effects.",
                "summary": "Ecological and health impacts are not yet fully understood.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "Crypto-currencies",
        "url": "https://fin-tech.io/crypto",
        "html": "<html>...</html>",
        "readability": "<p>Financial sovereignty.</p><p>Wastes energy.</p>",
        "arguments": [
            {
                "text": "Financial sovereignty.",
                "summary": "Decentralized money cannot be censored by governments.",
                "stance": "pour"
            },
            {
                "text": "Wastes energy.",
                "summary": "Proof of work consensus consumes electricity comparable to nations.",
                "stance": "contre"
            }
        ]
    },
    {
        "topic": "Car-free Cities",
        "url": "https://urban-planning.org/carfree",
        "html": "<html>...</html>",
        "readability": "<p>Walkable and safe streets.</p><p>Hard for elderly/disabled.</p>",
        "arguments": [
            {
                "text": "Walkable and safe streets.",
                "summary": "Removing cars reclaims public space for people and nature.",
                "stance": "pour"
            },
            {
                "text": "Hard for elderly/disabled.",
                "summary": "Cars provide essential door-to-door mobility for some groups.",
                "stance": "contre"
            }
        ]
    }
]

def run():
    print("Deleting old data...")
    Page.objects.all().delete()
    
    print("Creating mock data...")
    for scenario in SCENARIOS:
        print(f"  -> Creating page: {scenario['topic']}")
        page = Page.objects.create(
            url=scenario['url'],
            html_original=scenario['html'],
            html_readability=scenario['readability'],
            text_readability=scenario['readability'] # simplifying for mock
        )

        for i, arg_data in enumerate(scenario['arguments']):
            # Create a fake block for the argument
            selector = f"p:nth-child({i+1})"
            text = arg_data['text']
            
            block = TextBlock.objects.create(
                page=page,
                selector=selector,
                start_offset=0,
                end_offset=len(text),
                text=text
            )
            
            Argument.objects.create(
                page=page,
                text_block=block,
                selector=selector,
                start_offset=0,
                end_offset=len(text),
                text_original=text,
                summary=arg_data['summary'],
                stance=arg_data['stance']
            )

    print("Done! Created 10 scenarios with pages, blocks and arguments.")

if __name__ == '__main__':
    run()
