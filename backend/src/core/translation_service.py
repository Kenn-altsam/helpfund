"""
Translation service for city names

Maps English city names to their Russian equivalents used in the database.
Provides functionality to translate user input before database searches.
"""

from typing import Dict, Optional, List
import re


class CityTranslationService:
    """Service for translating city names from English to Russian"""
    
    # Mapping of English city names to Russian equivalents
    # This includes major Kazakh cities and their common English spellings
    CITY_TRANSLATIONS: Dict[str, str] = {
        # Major cities
        "almaty": "Алматы",
        "astana": "Астана", 
        "nur-sultan": "Нур-Султан",
        "nursultan": "Нур-Султан",
        "shymkent": "Шымкент",
        "aktobe": "Актобе",
        "taraz": "Тараз",
        "pavlodar": "Павлодар", 
        "ust-kamenogorsk": "Усть-Каменогорск",
        "oskemen": "Оскемен",
        "semey": "Семей",
        "atyrau": "Атырау",
        "kostanay": "Костанай",
        "petropavl": "Петропавл",
        "karaganda": "Караганда",
        "aktau": "Актау",
        "kyzylorda": "Кызылорда",
        "uralsk": "Уральск",
        "oral": "Орал",
        "turkestan": "Туркестан",
        "ekibastuz": "Экибастуз",
        
        # Regions/Oblast centers
        "akmola": "Акмола", 
        "akmola region": "Акмолинская область",
        "akmola oblast": "Акмолинская область",
        "aktobe region": "Актюбинская область",
        "aktobe oblast": "Актюбинская область",
        "almaty region": "Алматинская область", 
        "almaty oblast": "Алматинская область",
        "atyrau region": "Атырауская область",
        "atyrau oblast": "Атырауская область",
        "east kazakhstan": "Восточно-Казахстанская область",
        "east kazakhstan region": "Восточно-Казахстанская область",
        "jambyl region": "Жамбылская область",
        "jambyl oblast": "Жамбылская область",
        "zhambyl region": "Жамбылская область",
        "zhambyl oblast": "Жамбылская область",
        "karaganda region": "Карагандинская область",
        "karaganda oblast": "Карагандинская область", 
        "kostanay region": "Костанайская область",
        "kostanay oblast": "Костанайская область",
        "kyzylorda region": "Кызылординская область",
        "kyzylorda oblast": "Кызылординская область",
        "mangystau region": "Мангыстауская область",
        "mangystau oblast": "Мангыстауская область",
        "north kazakhstan": "Северо-Казахстанская область",
        "north kazakhstan region": "Северо-Казахстанская область",
        "pavlodar region": "Павлодарская область",
        "pavlodar oblast": "Павлодарская область",
        "south kazakhstan": "Южно-Казахстанская область", 
        "south kazakhstan region": "Южно-Казахстанская область",
        "west kazakhstan": "Западно-Казахстанская область",
        "west kazakhstan region": "Западно-Казахстанская область",
        
        # Common smaller cities
        "stepnogorsk": "Степногорск",
        "kokshetau": "Кокшетау",
        "kokchetav": "Кокшетау",
        "temirtau": "Темиртау",
        "rudny": "Рудный",
        "zhezkazgan": "Жезказган",
        "balkhash": "Балхаш",
        "taldykorgan": "Талдыкорган",
        "kapchagai": "Капчагай",
        "kentau": "Кентау",
        "arys": "Арыс",
        "shu": "Шу",
        "zhanaozen": "Жанаозен",
        "beyneu": "Бейнеу",
        "fort-shevchenko": "Форт-Шевченко",
        "lisakovsk": "Лисаковск",
        "arkalyk": "Аркалык",
        "mamlyutka": "Мамлютка",
        "shalkar": "Шалкар",
        "esil": "Есиль",
        "makinsk": "Макинск",
        "stepnyak": "Степняк",
        "schuchinsk": "Щучинск",
        "borodulikha": "Бородулиха",
        "ridder": "Риддер",
        "zyryanovsk": "Зыряновск",
        "ayagoz": "Аягоз",
        "georgievka": "Георгиевка",
        "kurchatov": "Курчатов",
        "iron": "Железинка",
        "iron city": "Железинка",
        "aktogay": "Актогай",
        "karkaralinsk": "Каракаралинск",
        "saran": "Саран",
        "abay": "Абай",
        "shahtinsk": "Шахтинск",
        "jezkazgan": "Жезказган",
        "priozersk": "Приозерск",
        "baikonur": "Байконур",
        "kazalinsk": "Казалинск",
        "aralsk": "Аральск",
    }
    
    @classmethod
    def translate_city_name(cls, city_name: str) -> str:
        """
        Translate English city name to Russian equivalent
        
        Args:
            city_name: City name in English or other language
            
        Returns:
            Russian city name if translation found, otherwise original name
        """
        if not city_name:
            return city_name
            
        # Normalize the input - convert to lowercase and strip spaces
        normalized_name = city_name.lower().strip()
        
        # Direct translation lookup
        if normalized_name in cls.CITY_TRANSLATIONS:
            return cls.CITY_TRANSLATIONS[normalized_name]
            
        # Try partial matches for compound names or regions
        for english_name, russian_name in cls.CITY_TRANSLATIONS.items():
            if english_name in normalized_name or normalized_name in english_name:
                return russian_name
                
        # If no translation found, return original
        return city_name
    
    @classmethod
    def get_all_possible_names(cls, city_name: str) -> List[str]:
        """
        Get all possible name variations for searching
        
        Args:
            city_name: Input city name
            
        Returns: 
            List of possible name variations including original and translated
        """
        names = [city_name]  # Always include original
        
        # Add translated version if different
        translated = cls.translate_city_name(city_name)
        if translated != city_name:
            names.append(translated)
            
        # Add case variations
        names.extend([
            city_name.lower(), 
            city_name.title(),
            translated.lower() if translated != city_name else None,
            translated.title() if translated != city_name else None
        ])
        
        # Remove None values and duplicates
        return list(set(filter(None, names)))
    
    @classmethod
    def add_translation(cls, english_name: str, russian_name: str) -> None:
        """
        Add a new translation mapping
        
        Args:
            english_name: English city name (will be normalized to lowercase)
            russian_name: Russian city name
        """
        cls.CITY_TRANSLATIONS[english_name.lower().strip()] = russian_name
    
    @classmethod 
    def get_supported_cities(cls) -> List[str]:
        """
        Get list of supported English city names
        
        Returns:
            List of English city names that have translations
        """
        return list(cls.CITY_TRANSLATIONS.keys()) 