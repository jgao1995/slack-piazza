# Piazza and Slack integration

## Usage

Create a file called `config.py` in the working directory with the following format:

```python
piazza_username = 'user@email'
piazza_password = 'password'

piazza_class_id = 'XXXXXXXXXXXXXXXXX'

# add this line to use `linker_bot.py`
slack_bot_token = 'xoxb-XXXXXXXXXXXXXXXXX'

# add this line to use `slash_command.py`
slash_command_expected_slack_token = 'XXXXXXXXXXXXXXXXX'
```
