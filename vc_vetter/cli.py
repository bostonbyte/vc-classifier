import concurrent.futures
import logging
import os
import sys
from typing import Dict, Any, Tuple
import pandas as pd
from tqdm import tqdm
from vc_vetter.config import Settings
from vc_vetter.scraper import VCWebScraper
from vc_vetter.vetter import VCVetter

try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

logger = logging.getLogger(__name__)

class CLIRunner:
    """Handles the Command Line Interface lifecycle for the vetting process."""
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.scraper = VCWebScraper(self.settings)

    def get_startup_info(self) -> str:
        """Gathers the user's startup details via command-line prompts.
        
        Returns:
            A formatted string containing the startup profile.
        """
        print("\n" + "="*45)
        print("     STARTUP DETAILS PROFILE CREATION     ")
        print("="*45)
        
        product_name = input("1. Product Name: ").strip() or "Unnamed Startup"
        value_proposition = input("2. Value Proposition (1-2 sentences): ").strip()
        target_market = input("3. Target Market (B2B or B2C): ").strip() or "B2B"
        market_size = input("4. Market Size (e.g., $10B): ").strip() or "Unknown"
        amount_to_raise = input("5. Amount to Raise (e.g., $2M): ").strip() or "Unknown"
        investment_round = input("6. Round (e.g., Seed, Series A): ").strip() or "Seed"
        
        startup_details = (
            f"- Product: {product_name}\n"
            f"- Value Proposition: {value_proposition}\n"
            f"- Target Market: {target_market}\n"
            f"- Market Size: {market_size}\n"
            f"- Fundraising Amount: {amount_to_raise}\n"
            f"- Fundraising Round: {investment_round}\n"
        )
        print("\n--- Profile Created. Initializing vetting pipeline. ---\n")
        return startup_details

    def _process_single_vc(self, item: Tuple[int, pd.Series], startup_profile: str, vetter: VCVetter) -> Dict[str, Any]:
        """Task worker function to scrape a single VC website and determine fit using LLM.
        
        Args:
            item: A tuple of (index, row) from the Pandas dataframe iterrows.
            startup_profile: The formatted profile of the startup.
            vetter: Pre-instantiated VCVetter object.
            
        Returns:
            Dictionary containing original row data enriched with 'Good fit' and 'Reasoning'.
        """
        index, row = item
        vc_name = row.get('Investor name', row.get('Fund Name', f"VC #{index + 1}"))
        website_url = row.get('Website', '').strip()
        
        result = row.to_dict()
        
        if not website_url:
            logger.warning(f"Skipping {vc_name}: No website URL provided.")
            result['Good fit'] = "No"
            result['Reasoning'] = "No website URL provided in the dataset."
            return result

        try:
            logger.info(f"Vetting: {vc_name} ({website_url})")
            scraped_text = self.scraper.crawl_and_scrape(website_url)
            
            decision = vetter.analyze_fit(scraped_text, startup_profile)
            
            result['Good fit'] = "Yes" if decision.is_fit else "No"
            result['Reasoning'] = decision.reasoning
            
        except Exception as e:
            logger.error(f"Unexpected error vetting {vc_name}: {e}")
            result['Good fit'] = "Error"
            result['Reasoning'] = f"Vetting execution failed: {str(e)}"
            
        return result

    def run(self):
        """Runs the primary CLI execution loop."""
        # 1. Get Startup Profile details
        startup_profile = self.get_startup_info()
        
        # 2. Ask user for dataset path
        input_file = input("Enter the path to your CSV or Excel file of VCs: ").strip()
        if not os.path.exists(input_file):
            print(f"Error: The file '{input_file}' was not found.")
            sys.exit(1)
            
        # 3. Read dataset
        try:
            if input_file.lower().endswith('.csv'):
                df = pd.read_csv(input_file, dtype=str).fillna('')
            elif input_file.lower().endswith(('.xls', '.xlsx')):
                df = pd.read_excel(input_file, dtype=str).fillna('')
            else:
                raise ValueError("Unsupported file format. Please use a CSV or Excel (.xlsx) file.")
        except Exception as e:
            print(f"Error reading file '{input_file}': {e}")
            sys.exit(1)

        # Standardize headers (find column named 'website' case-insensitively)
        website_col = None
        for col in df.columns:
            if col.lower() == 'website':
                website_col = col
                break
                
        if not website_col:
            print("Error: The input file must contain a 'Website' column.")
            sys.exit(1)

        if website_col != 'Website':
            df = df.rename(columns={website_col: 'Website'})

        print(f"Loaded {len(df)} VCs from dataset.")
        print(f"Starting parallel processing using {self.settings.max_workers} threads...")
        
        # 4. Instantiate LLM and Vetter
        try:
            shared_llm = ChatOllama(model=self.settings.local_llm_model, temperature=0.0)
            vetter = VCVetter(self.settings, llm=shared_llm)
        except Exception as e:
            print(f"\nFailed to initialize Ollama model '{self.settings.local_llm_model}': {e}")
            print("Troubleshooting steps:")
            print("1. Ensure the Ollama app is running locally.")
            print(f"2. Pull the model manually using: ollama pull {self.settings.local_llm_model}")
            sys.exit(1)

        tasks = list(df.iterrows())
        final_results = []

        # 5. Run Executor
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            future_to_vc = {
                executor.submit(self._process_single_vc, task, startup_profile, vetter): task 
                for task in tasks
            }
            
            # Use tqdm progress bar overlay
            for future in tqdm(concurrent.futures.as_completed(future_to_vc), total=len(tasks), desc="Vetting progress"):
                final_results.append(future.result())

        # 6. Save final report
        output_df = pd.DataFrame(final_results)
        output_file = "vc_vetting_results_final.csv"
        try:
            output_df.to_csv(output_file, index=False)
            print("\n" + "="*45)
            print("           PROCESSING COMPLETED           ")
            print("="*45)
            print(f"Vetted results successfully written to '{output_file}'\n")
        except Exception as e:
            print(f"Error saving results file to '{output_file}': {e}")
            sys.exit(1)
