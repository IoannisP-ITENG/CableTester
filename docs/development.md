# Working with the source

## Project structure

```markdown
📦<root>
 ┣ 📂build `Here you can find the "usefull" files after building this project localy`
 ┃ ┣ 📂faebryk
 ┃ ┣ 📂kicad
 ┣ 📂docs `Project documentation is placed in this folder`
 ┣ 📂source
 ┃ ┣ 📂faebryk
 ┃ ┃ ┣ 📂library
 ┃ ┃ ┃ ┣ 📂library
 ┃ ┃ ┃ ┃ ┗ 📜components.py `In this file you can put the components that are not in the standard faebryk library`
 ┃ ┃ ┣ 📂modules
 ┃ ┃ ┗ 📜main.py `This is the main faberyk file of this project. Any changes should be made here`
 ┃ ┣ 📂kicad `KiCad project files`
 ┃ ┃ ┗ 📂main
 ┃ ┃ ┃ ┣ 📜main.kicad_pcb
 ┃ ┃ ┃ ┣ 📜main.kicad_pro
 ┃ ┃ ┃ ┣ 📜main.kicad_sch
 ┣ 📜.gitignore
 ┣ 📜render.png
 ┣ 📜overview.png
 ┣ 📜LICENSE
 ┣ 📜README.md `Project "homepage"`
 ┗ 📜requirements.txt `Required python/pip packages`
```

## Prerequisites

To start working on this project you will need the following.

### Step 1

Install the following programs:

- [Visual Studio Code](https://code.visualstudio.com/)
- [Python 3](https://www.python.org/) (add to PATH)
- [KiCad 6](https://www.kicad.org/)
- [git](https://git-scm.com/)

### Step 2

Clone this repository and install the requirements

```bash
git clone <url>
```

```bash
cd <project>

# create venv (optional)
mkdir .local
python -m venv .local/venv
source .local/venv/bin/activate

pip install -r requirements.txt
```

### Step 3

Run the project to see if everything is installed correctly

```bash
python3 ./source/faebryk/main.py
```

This should output a netlist file in the `./build/faebryk/netlist/` folder.

### Step 4

Check if KiCad works

Open the `./source/kicad/main.prj` file in KiCad.

## Editing the project

The file you will work with most is the `./source/faebryk/main.py`. Here you describe your design in faebryk.

If you want to create your own components, traits or modules specific to this project you can place them in `./source/faebryk/library/<thing you want to add>`.

The PCB layout can be eddited in KiCad 6 by edditing the `./souce/kicad/main/main.kicad_pcb` file. If you changed anything in the faebryk source, you have to re-import the netlist into KiCad like so:

- `file > import > netlist`
- Select the file `./build/faebryk/faebryk.net`
- Press `Load and Test Netlist`
- If there are no errors, press `Update PCB`

## Running the project

To run the project and output the build files do as follow:

```bash
python ./source/faebryk/main.py
```

The output files will be in `./build/faebryk/`
